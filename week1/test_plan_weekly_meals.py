"""Unit tests for plan_weekly_meals tool."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from server import plan_weekly_meals, _format_meal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _make_meal(id: int, title: str, minutes: int = 30, servings: int = 4) -> dict:
    return {
        "id": id,
        "title": title,
        "readyInMinutes": minutes,
        "servings": servings,
        "sourceUrl": f"https://example.com/{id}",
    }


def _make_week_response(target_calories: int = 2000) -> dict:
    """Build a realistic mealplanner/generate response."""
    week = {}
    meal_id = 100
    for day in DAYS:
        meals = [
            _make_meal(meal_id, f"{day.title()} Breakfast", 15, 2),
            _make_meal(meal_id + 1, f"{day.title()} Lunch", 30, 4),
            _make_meal(meal_id + 2, f"{day.title()} Dinner", 45, 4),
        ]
        week[day] = {
            "meals": meals,
            "nutrients": {
                "calories": target_calories + 10.5,
                "protein": 120.3,
                "fat": 65.2,
                "carbohydrates": 230.1,
            },
        }
        meal_id += 3
    return {"week": week}


# ---------------------------------------------------------------------------
# _format_meal helper
# ---------------------------------------------------------------------------
class TestFormatMeal:
    def test_extracts_fields(self):
        meal = _make_meal(42, "Test Meal", 20, 2)
        result = _format_meal(meal)
        assert result == {
            "id": 42,
            "title": "Test Meal",
            "readyInMinutes": 20,
            "servings": 2,
            "sourceUrl": "https://example.com/42",
        }

    def test_missing_fields_default_to_none(self):
        result = _format_meal({})
        assert result["id"] is None
        assert result["title"] is None
        assert result["sourceUrl"] == ""


# ---------------------------------------------------------------------------
# plan_weekly_meals tool
# ---------------------------------------------------------------------------
class TestPlanWeeklyMeals:
    @pytest.mark.asyncio
    async def test_returns_7_days_with_3_meals_each(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response):
            raw = await plan_weekly_meals()
        result = json.loads(raw)

        assert len(result["week"]) == 7
        for day in DAYS:
            assert day in result["week"]
            assert len(result["week"][day]["meals"]) == 3

    @pytest.mark.asyncio
    async def test_all_recipe_ids_contains_21_ids(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response):
            raw = await plan_weekly_meals()
        result = json.loads(raw)

        assert len(result["all_recipe_ids"]) == 21
        assert all(isinstance(rid, int) for rid in result["all_recipe_ids"])

    @pytest.mark.asyncio
    async def test_nutrients_present_per_day(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response):
            raw = await plan_weekly_meals()
        result = json.loads(raw)

        for day in DAYS:
            nutrients = result["week"][day]["nutrients"]
            assert "calories" in nutrients
            assert "protein" in nutrients
            assert "fat" in nutrients
            assert "carbohydrates" in nutrients
            assert nutrients["calories"] > 0

    @pytest.mark.asyncio
    async def test_target_calories_passed_through(self):
        mock_response = _make_week_response(1500)
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            raw = await plan_weekly_meals(target_calories=1500)
        result = json.loads(raw)

        assert result["target_calories"] == 1500
        call_params = mock_get.call_args[0][1]
        assert call_params["targetCalories"] == 1500

    @pytest.mark.asyncio
    async def test_target_calories_clamped(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            raw = await plan_weekly_meals(target_calories=500)
        result = json.loads(raw)

        assert result["target_calories"] == 1200
        call_params = mock_get.call_args[0][1]
        assert call_params["targetCalories"] == 1200

    @pytest.mark.asyncio
    async def test_diet_param_forwarded(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await plan_weekly_meals(diet="vegetarian")

        call_params = mock_get.call_args[0][1]
        assert call_params["diet"] == "vegetarian"

    @pytest.mark.asyncio
    async def test_exclude_param_forwarded(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await plan_weekly_meals(exclude="shellfish, olives")

        call_params = mock_get.call_args[0][1]
        assert call_params["exclude"] == "shellfish, olives"

    @pytest.mark.asyncio
    async def test_empty_diet_and_exclude_not_sent(self):
        mock_response = _make_week_response()
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await plan_weekly_meals(diet="", exclude="")

        call_params = mock_get.call_args[0][1]
        assert "diet" not in call_params
        assert "exclude" not in call_params

    @pytest.mark.asyncio
    async def test_api_error_returns_error_string(self):
        with patch("server._spoonacular_get", new_callable=AsyncMock, side_effect=RuntimeError("SPOONACULAR_API_KEY is not set.")):
            raw = await plan_weekly_meals()

        assert raw.startswith("Error:")
        assert "SPOONACULAR_API_KEY" in raw

    @pytest.mark.asyncio
    async def test_empty_week_data_handled(self):
        with patch("server._spoonacular_get", new_callable=AsyncMock, return_value={"week": {}}):
            raw = await plan_weekly_meals()
        result = json.loads(raw)

        assert len(result["week"]) == 7
        for day in DAYS:
            assert result["week"][day]["meals"] == []
            assert result["week"][day]["nutrients"]["calories"] == 0
        assert result["all_recipe_ids"] == []
