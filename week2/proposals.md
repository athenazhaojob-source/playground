# Solution Proposals — `plan_weekly_meals` Tool

**Date:** 2026-03-24

---

**Context:**
- **Request:** Add a `plan_weekly_meals` tool that generates a 7-day meal plan with balanced nutrition using Spoonacular's meal plan API endpoint.
- **Research Source:** `research/codebase-research.md` — sections 2a (server architecture, helpers, tool patterns), 2c (price table), 3 (data flow).

---

## Proposal 1 — Direct `mealplanner/generate` endpoint

**Overview:**
Call Spoonacular's `GET /mealplanner/generate` with `timeFrame=week`. This endpoint returns 3 meals/day for 7 days with calorie targets already balanced. It requires a single API call, fits the existing `_spoonacular_get()` helper, and follows the same tool pattern as the other four tools.

**Key Changes:**
- `week1/server.py` — Add one Pydantic input model (`PlanWeeklyMealsInput`) and one `@mcp.tool` function (~60-80 lines)
- `week1/test_client.py` — Add a Step 4 that calls `plan_weekly_meals` and prints the 7-day grid
- `week1/README.md` — Add the new tool to the tools table

**Parameters:**
```
target_calories: int  (default 2000, range 1200-4000)
diet: Optional[str]   (reuse existing diet enum from filter_by_diet)
exclude: Optional[str] (comma-separated ingredients to exclude)
```

**Return shape:**
```json
{
  "week": {
    "monday": { "meals": [...], "nutrients": {"calories": N, "protein": N, ...} },
    ...
  },
  "total_estimated_cost": 123.45
}
```

Each meal object reuses `_recipe_summary()` for consistency. Optionally chains into `cost_estimate` by collecting all recipe ingredient names.

**Trade-offs:**
| Benefit | Risk |
|---------|------|
| Single API call (~1 point) — fits free-tier budget | Spoonacular controls the balancing algorithm; no way to customize meal distribution |
| Minimal code — reuses `_spoonacular_get()`, `_handle_error()`, `_cache` | The `mealplanner/generate` response shape differs from `complexSearch`; needs a dedicated response formatter |
| Nutritional data comes for free (calories, protein, fat, carbs per day) | Cache key will be large (includes all params); a 5-min TTL may be too short for a weekly plan |

**Validation:**
- Unit test: mock the Spoonacular response, verify 7 days x 3 meals structure and nutrient sums
- Integration test: extend `test_client.py` with a Step 4 calling the new tool
- Edge cases: missing `diet` param, `exclude` containing items not in any recipe, calorie target at boundaries

**Open Questions:**
- Does the free tier charge extra points for the `mealplanner/generate` endpoint? (Some Spoonacular endpoints cost more than 1 point.)
- Should the tool auto-chain into `generate_grocery_list` + `cost_estimate` for the full week, or leave that to the MCP client? Auto-chaining would be convenient but costs additional API calls per recipe.

---

## Proposal 2 — Composite plan built from `complexSearch`

**Overview:**
Build the weekly plan server-side by making multiple `recipes/complexSearch` calls (one per meal type: breakfast, lunch, dinner), distributing results across 7 days, and computing a calorie/nutrition summary from recipe metadata. This avoids a new API endpoint and reuses the exact code path that `suggest_meals` and `filter_by_diet` already exercise.

**Key Changes:**
- `week1/server.py` — Add one Pydantic model and one `@mcp.tool` function (~120-150 lines), plus a `_build_weekly_plan()` helper that distributes recipes across days
- `week1/server.py` — Extend `_recipe_summary()` to optionally include `nutrition` fields (`server.py:106-115`)
- `week1/test_client.py` — Add a Step 4
- `week1/README.md` — Update tools table

**Parameters:**
```
target_calories: int      (default 2000, range 1200-4000)
diet: Optional[str]       (reuse existing diet values)
exclude: Optional[str]    (comma-separated exclusions)
meals_per_day: int        (default 3, range 2-4)
```

**Approach detail:**
1. Call `recipes/complexSearch` 3 times with `type=breakfast`, `type=main course`, `type=main course` (or `snack` for 4-meal plans), `number=7`, `addRecipeNutrition=True`, plus optional `diet` and `excludeIngredients`
2. Distribute the 7 results from each meal-type search across Monday-Sunday
3. Sum per-day calories from the nutrition data Spoonacular returns with `addRecipeNutrition=True`
4. Return the same `{week, total_estimated_cost}` shape as Proposal 1

**Trade-offs:**
| Benefit | Risk |
|---------|------|
| Full control over meal distribution and variety logic | 3 API calls per invocation (~3 points) — higher quota usage |
| Reuses the exact `complexSearch` code path already tested | More code to write and maintain (~2x Proposal 1) |
| Can add custom balancing rules (e.g., no repeats, protein minimums) | Nutrition balancing is manual; must calculate and verify calorie targets yourself |
| `addRecipeNutrition=True` returns detailed macros per recipe | Heavier response payloads; may hit `CHARACTER_LIMIT` (25K) more easily |

**Validation:**
- Unit test: mock 3 search responses, verify 7-day distribution with no recipe repeats
- Unit test: verify daily calorie sums are within +/-20% of `target_calories`
- Integration test: extend `test_client.py`
- Edge case: fewer than 7 results returned for a meal type (e.g., niche diet + exclusion)

**Open Questions:**
- What balancing heuristic to use when Spoonacular returns recipes with wildly different calorie counts? Simple round-robin, or greedy knapsack toward the daily target?
- Should the tool deduplicate across meal types (e.g., prevent the same chicken recipe appearing as both lunch Monday and dinner Wednesday)?

---

## Recommendation

**Proposal 1** is the better starting point — it's a single API call, minimal code, and Spoonacular handles the nutritional balancing. If the free-tier point cost is acceptable, it delivers the feature with the least complexity. Proposal 2 becomes worth it only if you need custom distribution logic or find that `mealplanner/generate` doesn't return sufficient nutritional detail.
