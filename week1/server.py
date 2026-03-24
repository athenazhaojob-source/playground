#!/usr/bin/env python3
"""
Meal Planner MCP Server.

Exposes five tools via MCP:
  - suggest_meals: Search recipes via Spoonacular API
  - filter_by_diet: Find recipes matching dietary restrictions
  - generate_grocery_list: Consolidate ingredients from selected recipes
  - cost_estimate: Estimate grocery cost using a local price table
  - plan_weekly_meals: Generate a balanced 7-day meal plan

Requires: SPOONACULAR_API_KEY environment variable.
Free tier: 150 points/day (each search ~1 pt).
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server & constants
# ---------------------------------------------------------------------------
mcp = FastMCP("meal_planner_mcp")

API_BASE_URL = "https://api.spoonacular.com"
API_KEY = os.environ.get("SPOONACULAR_API_KEY", "")
CHARACTER_LIMIT = 25_000
PRICES_PATH = Path(__file__).parent / "prices.json"

# Simple in-memory cache: key -> (timestamp, data)
_cache: Dict[str, tuple[float, Any]] = {}
CACHE_TTL = 300  # 5 minutes


def _load_prices() -> Dict[str, float]:
    """Load the local price table (JSON)."""
    with open(PRICES_PATH) as f:
        return json.load(f)


def _cache_get(key: str) -> Any | None:
    """Return cached value if still fresh, else None."""
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
async def _spoonacular_get(endpoint: str, params: dict | None = None) -> dict:
    """Make an authenticated GET request to Spoonacular."""
    api_key = os.environ.get("SPOONACULAR_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SPOONACULAR_API_KEY is not set. "
            "Get a free key at https://spoonacular.com/food-api/console"
        )
    params = params or {}
    params["apiKey"] = api_key

    cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{API_BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        data = resp.json()

    _cache_set(cache_key, data)
    return data


def _handle_error(e: Exception) -> str:
    """Consistent, actionable error messages."""
    if isinstance(e, RuntimeError):
        return f"Error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "Error: Invalid API key. Check SPOONACULAR_API_KEY."
        if code == 402:
            return "Error: Daily API quota exhausted (free tier = 150 pts/day). Try again tomorrow."
        if code == 429:
            return "Error: Rate limited. Wait a moment and retry."
        return f"Error: Spoonacular API returned HTTP {code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Try again."
    return f"Error: {type(e).__name__}: {e}"


def _recipe_summary(r: dict) -> dict:
    """Extract a compact summary from a Spoonacular recipe object."""
    return {
        "id": r.get("id"),
        "title": r.get("title"),
        "readyInMinutes": r.get("readyInMinutes"),
        "servings": r.get("servings"),
        "sourceUrl": r.get("sourceUrl", ""),
        "image": r.get("image", ""),
    }


def _format_meal(meal: dict) -> dict:
    """Extract a compact summary from a mealplanner meal object."""
    return {
        "id": meal.get("id"),
        "title": meal.get("title"),
        "readyInMinutes": meal.get("readyInMinutes"),
        "servings": meal.get("servings"),
        "sourceUrl": meal.get("sourceUrl", ""),
    }


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------
class SuggestMealsInput(BaseModel):
    """Input for meal suggestion search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description="Free-text search (e.g. 'pasta', 'chicken stir fry', 'quick breakfast')",
        min_length=1,
        max_length=200,
    )
    number: int = Field(
        default=5,
        description="Number of results to return (1-10)",
        ge=1,
        le=10,
    )


class FilterByDietInput(BaseModel):
    """Input for diet-filtered recipe search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    diet: str = Field(
        ...,
        description=(
            "Diet type: vegetarian, vegan, glutenFree, dairyFree, "
            "ketogenic, paleo, whole30, pescetarian, lactoVegetarian, "
            "ovoVegetarian"
        ),
        min_length=1,
        max_length=50,
    )
    query: Optional[str] = Field(
        default=None,
        description="Optional keyword to narrow results (e.g. 'soup', 'salad')",
        max_length=200,
    )
    number: int = Field(
        default=5,
        description="Number of results to return (1-10)",
        ge=1,
        le=10,
    )

    @field_validator("diet")
    @classmethod
    def normalise_diet(cls, v: str) -> str:
        return v.strip().lower()


class GroceryListInput(BaseModel):
    """Input for grocery list generation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    recipe_ids: list[int] = Field(
        ...,
        description="List of Spoonacular recipe IDs (get these from suggest_meals or filter_by_diet)",
        min_length=1,
        max_length=20,
    )


class CostEstimateInput(BaseModel):
    """Input for grocery cost estimation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ingredients: list[str] = Field(
        ...,
        description="List of ingredient names (e.g. ['chicken breast', 'rice', 'broccoli'])",
        min_length=1,
        max_length=100,
    )


class PlanWeeklyMealsInput(BaseModel):
    """Input for weekly meal plan generation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    target_calories: int = Field(
        default=2000,
        description="Daily calorie target (1200-4000)",
        ge=1200,
        le=4000,
    )
    diet: Optional[str] = Field(
        default=None,
        description=(
            "Diet type: vegetarian, vegan, glutenFree, dairyFree, "
            "ketogenic, paleo, whole30, pescetarian"
        ),
        max_length=50,
    )
    exclude: Optional[str] = Field(
        default=None,
        description="Comma-separated ingredients to exclude (e.g. 'shellfish, olives')",
        max_length=500,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool(
    name="suggest_meals",
    annotations={
        "title": "Suggest Meals",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def suggest_meals(
    query: str,
    number: int = 5,
) -> str:
    """Search for meal ideas by keyword.

    Returns a list of recipes matching the query, including title,
    cook time, servings, and a source URL.  Use the returned recipe
    IDs with generate_grocery_list to get ingredients.

    Args:
        query: Free-text search (e.g. 'pasta', 'chicken stir fry', 'quick breakfast')
        number: Number of results to return, 1-10 (default 5)

    Returns:
        JSON array of recipe summaries, each containing:
        {id, title, readyInMinutes, servings, sourceUrl, image}
    """
    try:
        data = await _spoonacular_get(
            "recipes/complexSearch",
            {
                "query": query,
                "number": min(max(number, 1), 10),
                "addRecipeInformation": True,
            },
        )
        recipes = [_recipe_summary(r) for r in data.get("results", [])]
        if not recipes:
            return f"No recipes found for '{query}'. Try a broader search term."
        return json.dumps(recipes, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="filter_by_diet",
    annotations={
        "title": "Filter Recipes by Diet",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def filter_by_diet(
    diet: str,
    query: str = "",
    number: int = 5,
) -> str:
    """Find recipes that match a specific dietary restriction.

    Supports: vegetarian, vegan, glutenFree, dairyFree, ketogenic,
    paleo, whole30, pescetarian, lactoVegetarian, ovoVegetarian.

    Args:
        diet: Diet type (e.g. 'vegan', 'glutenFree', 'ketogenic')
        query: Optional keyword to narrow results (e.g. 'soup', 'salad')
        number: Number of results to return, 1-10 (default 5)

    Returns:
        JSON array of recipe summaries matching the diet.
    """
    try:
        diet = diet.strip().lower()
        api_params: dict[str, Any] = {
            "diet": diet,
            "number": min(max(number, 1), 10),
            "addRecipeInformation": True,
        }
        if query:
            api_params["query"] = query

        data = await _spoonacular_get("recipes/complexSearch", api_params)
        recipes = [_recipe_summary(r) for r in data.get("results", [])]
        if not recipes:
            hint = f" for '{query}'" if query else ""
            return f"No {diet} recipes found{hint}. Try a different query or diet."
        return json.dumps(recipes, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="generate_grocery_list",
    annotations={
        "title": "Generate Grocery List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def generate_grocery_list(
    recipe_ids: list[int],
) -> str:
    """Build a consolidated grocery list from one or more recipes.

    Fetches full ingredient data for each recipe ID, then merges
    duplicate ingredients and groups by aisle.  Use recipe IDs
    obtained from suggest_meals or filter_by_diet.

    Args:
        recipe_ids: List of Spoonacular recipe IDs (from suggest_meals or filter_by_diet)

    Returns:
        JSON object with:
        {
          "recipes": ["Recipe Title", ...],
          "ingredients": [
            {"name": "chicken breast", "amount": 2.0, "unit": "lbs", "aisle": "Meat"},
            ...
          ],
          "total_items": int
        }
    """
    try:
        all_ingredients: dict[str, dict] = {}
        recipe_titles: list[str] = []

        for rid in recipe_ids:
            data = await _spoonacular_get(f"recipes/{rid}/information")
            recipe_titles.append(data.get("title", f"Recipe {rid}"))

            for ing in data.get("extendedIngredients", []):
                name = ing.get("name", "").lower().strip()
                if not name:
                    continue
                if name in all_ingredients:
                    all_ingredients[name]["amount"] += ing.get("amount", 0)
                else:
                    all_ingredients[name] = {
                        "name": name,
                        "amount": round(ing.get("amount", 0), 2),
                        "unit": ing.get("unit", ""),
                        "aisle": ing.get("aisle", "Other"),
                    }

        ingredients = sorted(all_ingredients.values(), key=lambda x: x["aisle"])
        result = json.dumps(
            {
                "recipes": recipe_titles,
                "ingredients": ingredients,
                "total_items": len(ingredients),
            },
            indent=2,
        )

        if len(result) > CHARACTER_LIMIT:
            ingredients = ingredients[:50]
            result = json.dumps(
                {
                    "recipes": recipe_titles,
                    "ingredients": ingredients,
                    "total_items": len(ingredients),
                    "truncated": True,
                    "message": "List truncated to 50 items. Use fewer recipe IDs.",
                },
                indent=2,
            )

        return result
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="cost_estimate",
    annotations={
        "title": "Estimate Grocery Cost",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cost_estimate(
    ingredients: list[str],
) -> str:
    """Estimate the total cost of a list of ingredients.

    Uses a local price table (prices.json) for per-item estimates.
    Ingredients not in the table get a default price.  Pass the
    ingredient names from generate_grocery_list output.

    Args:
        ingredients: List of ingredient names (e.g. ['chicken breast', 'rice', 'broccoli'])

    Returns:
        JSON object with:
        {
          "line_items": [{"ingredient": str, "price": float, "matched": bool}, ...],
          "total": float,
          "currency": "USD",
          "note": "Prices are rough estimates from a local table."
        }
    """
    try:
        prices = _load_prices()
        default_price = prices.get("default", 2.99)

        line_items = []
        total = 0.0

        for ing in ingredients:
            name = ing.lower().strip()
            # Try exact match, then substring match
            price = prices.get(name)
            matched = price is not None
            if price is None:
                # Fuzzy: check if any price-table key is contained in the ingredient name
                for key, val in prices.items():
                    if key == "default":
                        continue
                    if key in name or name in key:
                        price = val
                        matched = True
                        break
            if price is None:
                price = default_price

            line_items.append({
                "ingredient": ing,
                "price": price,
                "matched": matched,
            })
            total += price

        return json.dumps(
            {
                "line_items": line_items,
                "total": round(total, 2),
                "currency": "USD",
                "note": "Prices are rough estimates from a local table.",
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="plan_weekly_meals",
    annotations={
        "title": "Plan Weekly Meals",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def plan_weekly_meals(
    target_calories: int = 2000,
    diet: str = "",
    exclude: str = "",
) -> str:
    """Generate a balanced 7-day meal plan.

    Creates a weekly meal plan with 3 meals per day, balanced around
    a daily calorie target.  Returns per-day nutritional summaries
    and a flat list of all recipe IDs for use with generate_grocery_list.

    Args:
        target_calories: Daily calorie target, 1200-4000 (default 2000)
        diet: Optional diet type (e.g. 'vegetarian', 'vegan', 'ketogenic')
        exclude: Optional comma-separated ingredients to exclude (e.g. 'shellfish, olives')

    Returns:
        JSON object with:
        {
          "week": {
            "monday": {
              "meals": [{id, title, readyInMinutes, servings, sourceUrl}, ...],
              "nutrients": {calories, protein, fat, carbohydrates}
            },
            ...
          },
          "all_recipe_ids": [int, ...],
          "target_calories": int
        }
    """
    try:
        target_calories = min(max(target_calories, 1200), 4000)
        api_params: dict[str, Any] = {
            "timeFrame": "week",
            "targetCalories": target_calories,
        }
        if diet:
            api_params["diet"] = diet.strip().lower()
        if exclude:
            api_params["exclude"] = exclude.strip()

        data = await _spoonacular_get("mealplanner/generate", api_params)

        days = [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ]
        week: dict[str, Any] = {}
        all_recipe_ids: list[int] = []

        for day in days:
            day_data = data.get("week", {}).get(day, {})
            meals = [_format_meal(m) for m in day_data.get("meals", [])]
            nutrients = day_data.get("nutrients", {})
            week[day] = {
                "meals": meals,
                "nutrients": {
                    "calories": nutrients.get("calories", 0),
                    "protein": nutrients.get("protein", 0),
                    "fat": nutrients.get("fat", 0),
                    "carbohydrates": nutrients.get("carbohydrates", 0),
                },
            }
            all_recipe_ids.extend(m["id"] for m in meals if m["id"] is not None)

        return json.dumps(
            {
                "week": week,
                "all_recipe_ids": all_recipe_ids,
                "target_calories": target_calories,
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
