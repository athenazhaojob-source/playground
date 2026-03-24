# plan_weekly_meals Tool — Design Document

## Current Context
- `week1/server.py` is a FastMCP server exposing 4 tools (`suggest_meals`, `filter_by_diet`, `generate_grocery_list`, `cost_estimate`) backed by the Spoonacular API
- All tools follow the same pattern: `@mcp.tool` decorator with annotations, raw parameters (not Pydantic model args), try/except with `_handle_error()`, JSON string return
- API calls go through `_spoonacular_get()` which handles auth, caching (5-min TTL), and timeouts
- A corresponding Pydantic input model exists for each tool (used as schema documentation, not as function args)
- The server chains tools: search → grocery list → cost estimate. The new tool adds a higher-level entry point that produces a full weekly plan

## Requirements

### Functional Requirements
- New `plan_weekly_meals` tool that calls Spoonacular's `GET /mealplanner/generate` endpoint with `timeFrame=week`
- Accept `target_calories` (int, default 2000), optional `diet` (str), optional `exclude` (str, comma-separated ingredients)
- Return a 7-day plan with 3 meals/day, including per-day nutritional summaries (calories, protein, fat, carbs)
- Each meal includes recipe id, title, cook time, servings, and source URL (reuse `_recipe_summary()`)
- Output recipe IDs that can be passed directly to the existing `generate_grocery_list` tool

### Non-Functional Requirements
- Single API call per invocation (~1 point) to conserve free-tier quota
- Response fits within `CHARACTER_LIMIT` (25K chars) — a weekly plan with 21 meals is well within bounds
- Cached like all other endpoints via `_spoonacular_get()`

## Design Decisions

### 1. Use `mealplanner/generate` endpoint directly (Proposal 1)
Will use Spoonacular's dedicated meal plan endpoint because:
- Single API call returns a balanced 7-day plan with nutritional data
- Spoonacular handles calorie balancing — no custom distribution logic needed
- Consistent with existing pattern of thin wrappers around Spoonacular endpoints
- Alternative (Proposal 2: composite from multiple `complexSearch` calls) costs 3+ API points and requires manual nutrition balancing

### 2. Response formatter as a dedicated helper
Will add a `_format_meal()` helper because:
- The `mealplanner/generate` response shape differs from `complexSearch` — meals are nested under `week.monday`, `week.tuesday`, etc., each containing a `meals` array and a `nutrients` object
- Keeps the tool function clean, matching the pattern of `_recipe_summary()` for the other tools
- The helper extracts and normalizes each meal into the same `{id, title, readyInMinutes, servings, sourceUrl}` shape

### 3. Collect all recipe IDs in a top-level field
Will include a flat `all_recipe_ids` list in the response because:
- Allows MCP clients to pass the list directly to `generate_grocery_list` without parsing nested day structures
- Completes the tool chain: `plan_weekly_meals` → `generate_grocery_list` → `cost_estimate`

## Technical Design

### 1. Pydantic Input Model
```python
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
        description="Diet type: vegetarian, vegan, glutenFree, dairyFree, ketogenic, paleo, whole30, pescetarian",
        max_length=50,
    )
    exclude: Optional[str] = Field(
        default=None,
        description="Comma-separated ingredients to exclude (e.g. 'shellfish, olives')",
        max_length=500,
    )
```

### 2. Response Helper
```python
def _format_meal(meal: dict) -> dict:
    """Extract a compact summary from a mealplanner meal object."""
    return {
        "id": meal.get("id"),
        "title": meal.get("title"),
        "readyInMinutes": meal.get("readyInMinutes"),
        "servings": meal.get("servings"),
        "sourceUrl": meal.get("sourceUrl", ""),
    }
```

### 3. Tool Function
```python
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
```

### 4. Return Shape
```json
{
  "week": {
    "monday": {
      "meals": [
        {"id": 123, "title": "...", "readyInMinutes": 30, "servings": 4, "sourceUrl": "..."},
        ...
      ],
      "nutrients": {"calories": 1985.5, "protein": 120.3, "fat": 65.2, "carbohydrates": 230.1}
    },
    ...
  },
  "all_recipe_ids": [123, 456, ...],
  "target_calories": 2000
}
```

### 5. Files Changed
- `week1/server.py` (lines 1-12: update module docstring to list 5 tools; lines 118-197: add `PlanWeeklyMealsInput` after existing input models; lines 450-457: add `plan_weekly_meals` tool + `_format_meal` helper before the entry point)
- `week1/test_client.py` (lines 64-78: add Step 4 calling `plan_weekly_meals` and printing the Monday plan + total recipe IDs)
- `week1/README.md` (lines 17-22: add `plan_weekly_meals` to the tools table)

## Implementation Plan

1. Phase 1: Add the tool to `server.py`
   - Add `PlanWeeklyMealsInput` Pydantic model after `CostEstimateInput` (after line 197)
   - Add `_format_meal()` helper after `_recipe_summary()` (after line 115)
   - Add `plan_weekly_meals` tool function before the entry point block (before line 453)
   - Update the module docstring at line 5 to include `plan_weekly_meals`

2. Phase 2: Update test client
   - Add a Step 4 in `test_client.py` that calls `plan_weekly_meals` with default params
   - Print Monday's meals and the `all_recipe_ids` list
   - Optionally chain into `generate_grocery_list` with the returned IDs

3. Phase 3: Update documentation
   - Add `plan_weekly_meals` row to the tools table in `week1/README.md`

## Testing Strategy

### Integration Tests
- Run `test_client.py` end-to-end with a valid `SPOONACULAR_API_KEY`
- Verify `plan_weekly_meals` returns 7 days, each with 3 meals and a `nutrients` object
- Verify `all_recipe_ids` length equals 21 (7 days x 3 meals)
- Chain `all_recipe_ids` into `generate_grocery_list` to verify IDs are valid Spoonacular recipe IDs

## Observability
Not applicable — the existing `_handle_error()` pattern covers all error reporting needs.

## Security Considerations
No new concerns — API key handling is unchanged, all input is validated by Pydantic constraints and Spoonacular's API.

## References
- Spoonacular Meal Plan endpoint: `GET /mealplanner/generate` — params: `timeFrame`, `targetCalories`, `diet`, `exclude`
- Proposal 1 from the solution proposals discussion
- Research document: `research/codebase-research.md`
