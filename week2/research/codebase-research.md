# Codebase Research — AI Course Weekly Projects

**Date:** 2026-03-24

---

## Summary

This repository is an AI course project organized by weekly lessons. It currently contains one completed project (`week1/`) and one empty directory (`week2/`). The week 1 project is a **Meal Planner MCP Server** built with Python's FastMCP framework, backed by the Spoonacular API for recipe data and a local JSON price table for cost estimation. The server exposes four chained tools over MCP (Model Context Protocol) for recipe search, dietary filtering, grocery list generation, and cost estimation. A test client exercises all four tools in a 3-step REPL workflow.

---

## Project Structure

```
lesson1/
├── .gitignore              # Python + env exclusions
├── README.md               # Root index table linking to weekly projects
├── firebase-debug.log      # Firebase debug artifact (not gitignored by name, but *.log is)
├── research/               # (this document)
├── week1/
│   ├── README.md           # Full documentation for the MCP server
│   ├── server.py           # MCP server — 4 tools, ~457 lines
│   ├── test_client.py      # Stdio MCP client for end-to-end testing, ~82 lines
│   ├── prices.json         # Local price table — 87 entries + 1 default
│   ├── pyproject.toml      # Package config (meal-planner-mcp v0.1.0)
│   └── requirements.txt    # Flat dependency list (3 packages)
└── week2/                  # Empty, newly created
```

---

## Detailed Findings

### 1. Root Configuration

**`.gitignore`** (`/.gitignore:1-11`)
Ignores Python caches, build artifacts, virtual environments, `.env`/`.env.local`, `*.log`, and `.DS_Store`.

**`README.md`** (`/README.md:1-6`)
A single markdown table indexing weekly projects. Currently lists only week 1.

**`firebase-debug.log`** — Present on disk but covered by the `*.log` gitignore pattern.

---

### 2. Week 1 — Meal Planner MCP Server

#### 2a. Server (`week1/server.py`)

**Framework:** FastMCP from `mcp.server.fastmcp`. The server instance is named `"meal_planner_mcp"` (`server.py:28`).

**External API:** Spoonacular (`https://api.spoonacular.com`), authenticated via `SPOONACULAR_API_KEY` environment variable (`server.py:30-31`).

**Constants:**
| Constant | Value | Location |
|----------|-------|----------|
| `API_BASE_URL` | `https://api.spoonacular.com` | `server.py:30` |
| `CHARACTER_LIMIT` | 25,000 chars | `server.py:32` |
| `CACHE_TTL` | 300 seconds (5 min) | `server.py:37` |

**Caching:** In-memory dict `_cache` mapping string keys to `(timestamp, data)` tuples. Keys are constructed from `endpoint:serialized_params`. Cache is checked/set inside `_spoonacular_get()` (`server.py:36-57`).

**HTTP Client:** `httpx.AsyncClient` with a 30-second timeout, created per-request inside `_spoonacular_get()` (`server.py:79-81`).

**Error Handling:** Centralized in `_handle_error()` (`server.py:88-103`). Maps exception types to user-facing messages:
- `RuntimeError` → raw message (missing API key)
- `HTTPStatusError 401` → invalid API key
- `HTTPStatusError 402` → quota exhausted
- `HTTPStatusError 429` → rate limited
- `TimeoutException` → timeout message
- All others → generic `type(e).__name__: e`

**Pydantic Input Models** (`server.py:121-197`):
All models use `ConfigDict(str_strip_whitespace=True)`.

| Model | Fields | Validation |
|-------|--------|------------|
| `SuggestMealsInput` | `query` (str, 1-200), `number` (int, 1-10, default 5) | — |
| `FilterByDietInput` | `diet` (str, 1-50), `query` (optional str, max 200), `number` (int, 1-10, default 5) | `normalise_diet` field_validator lowercases/strips `diet` |
| `GroceryListInput` | `recipe_ids` (list[int], 1-20 items) | — |
| `CostEstimateInput` | `ingredients` (list[str], 1-100 items) | — |

> **Note:** The input models are defined but the tool functions accept raw parameters directly — the models are not used as function arguments. They serve as documentation/schema references.

**Tools:**

All four tools are decorated with `@mcp.tool()` and include MCP annotations (`readOnlyHint: True`, `destructiveHint: False`, `idempotentHint: True`).

1. **`suggest_meals`** (`server.py:202-244`)
   - Calls `recipes/complexSearch` with `addRecipeInformation=True`
   - Clamps `number` to 1-10 inline
   - Returns JSON array of recipe summaries via `_recipe_summary()` helper
   - Returns a plain-text message if no results found

2. **`filter_by_diet`** (`server.py:247-292`)
   - Same endpoint as `suggest_meals` but adds `diet` parameter
   - Strips/lowercases diet inline (duplicates the Pydantic validator logic)
   - `query` parameter is optional; only added to API call if non-empty

3. **`generate_grocery_list`** (`server.py:295-375`)
   - Fetches full recipe info for each ID via `recipes/{id}/information`
   - Merges duplicate ingredients by name (lowercased), summing amounts
   - Groups output by `aisle` field from Spoonacular
   - Truncates to 50 items if serialized JSON exceeds `CHARACTER_LIMIT` (25K chars)
   - Returns `{recipes, ingredients, total_items}` (plus `truncated` + `message` if clipped)

4. **`cost_estimate`** (`server.py:378-450`)
   - Loads `prices.json` on every call via `_load_prices()` (no caching of the price file)
   - Two-pass price matching: exact match first, then substring match (either direction)
   - Unmatched ingredients fall back to `default` price ($2.99)
   - Returns `{line_items, total, currency, note}`
   - `openWorldHint` is `False` (only tool with this setting — prices are local-only)

**`_recipe_summary()`** (`server.py:106-115`):
Extracts `{id, title, readyInMinutes, servings, sourceUrl, image}` from a Spoonacular recipe object.

**Entry point:** `mcp.run()` when executed directly (`server.py:456-457`).

---

#### 2b. Test Client (`week1/test_client.py`)

A standalone async script that launches `server.py` as a subprocess via MCP stdio transport.

**Connection setup** (`test_client.py:19-25`):
- Command: `python3 server.py`
- Inherits the full `os.environ` (expects `SPOONACULAR_API_KEY` to be set)

**Workflow** (`test_client.py:27-78`):
1. Lists all available tools and prints names/descriptions
2. Calls `suggest_meals` with `query="quick chicken dinner"`, `number=3`
3. Takes the first recipe's ID and calls `generate_grocery_list`
4. Extracts ingredient names and calls `cost_estimate`
5. Prints matched-price count vs total ingredients

**Output parsing:** All tool results are read from `result.content[0].text` and parsed with `json.loads()`.

---

#### 2c. Price Table (`week1/prices.json`)

A flat JSON object with 87 ingredient keys (all lowercase) mapping to USD float prices, plus a `"default": 2.99` fallback entry.

Price range: $0.29 (banana) to $9.99 (shrimp). Categories covered: proteins, grains, dairy, produce, oils, spices, baking, canned goods, nuts.

---

#### 2d. Package Configuration

**`pyproject.toml`** (`week1/pyproject.toml:1-19`):
- Name: `meal-planner-mcp`, version `0.1.0`
- License: MIT
- Requires Python >= 3.10
- Build system: setuptools + wheel
- Dependencies: `mcp[cli]>=1.0.0`, `httpx>=0.27.0`, `pydantic>=2.0.0`
- Dev extras: `pytest`, `pytest-asyncio`

**`requirements.txt`** (`week1/requirements.txt:1-3`):
Mirrors the `pyproject.toml` dependencies exactly — `mcp[cli]>=1.0.0`, `httpx>=0.27.0`, `pydantic>=2.0.0`.

---

### 3. Cross-Component Data Flow

```
User / MCP Client
    │
    ▼
test_client.py ──stdio──► server.py (FastMCP)
                              │
                    ┌─────────┼──────────┐
                    ▼         ▼          ▼
             suggest_meals  filter_by_diet  generate_grocery_list
                    │         │          │
                    └────┬────┘          │
                         ▼              ▼
                  Spoonacular API   Spoonacular API
                  (complexSearch)   (recipe/{id}/info)
                         │              │
                         ▼              ▼
                    _cache (in-memory, 5 min TTL)
                                        │
                                        ▼
                                  cost_estimate
                                        │
                                        ▼
                                  prices.json (local)
```

The intended workflow chains tools sequentially:
1. `suggest_meals` or `filter_by_diet` → recipe IDs
2. `generate_grocery_list(recipe_ids)` → ingredient names
3. `cost_estimate(ingredient_names)` → priced line items

---

### 4. Git History

Three commits on `main`:

| Hash | Message |
|------|---------|
| `df285f7` | first commit |
| `b145042` | week1: Meal Planner MCP server with 4 tools |
| `ef3b335` | reorganize: move week1 files into week1/ directory |

No branches, no tags, no remote tracking beyond origin.
