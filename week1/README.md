# Week 1 — Meal Planner MCP Server

A [FastMCP](https://gofastmcp.com) server that suggests meals, generates consolidated grocery lists, and estimates costs — powered by the [Spoonacular API](https://spoonacular.com/food-api) and a local price table. No complex setup required.

## How it works

The server exposes four tools over MCP that chain together into a natural meal-planning workflow:

1. **Search** for recipes by keyword or dietary restriction
2. **Generate** a merged grocery list from selected recipes
3. **Estimate** the total cost using a local price table

Results are cached in-memory (5 min TTL) to conserve Spoonacular's free-tier quota (150 points/day).

## Tools

| Tool | What it does |
|------|-------------|
| `suggest_meals` | Search recipes by keyword (e.g. "quick chicken dinner"). Returns id, title, cook time, servings, and source URL. |
| `filter_by_diet` | Find recipes matching a diet: vegetarian, vegan, glutenFree, dairyFree, ketogenic, paleo, whole30, pescetarian. |
| `generate_grocery_list` | Consolidate ingredients from one or more recipe IDs. Merges duplicates, groups by aisle. |
| `cost_estimate` | Estimate grocery cost from a list of ingredient names using a local price table (`prices.json`). |
| `plan_weekly_meals` | Generate a balanced 7-day meal plan with 3 meals/day, daily nutrition summaries, and a flat recipe-ID list for `generate_grocery_list`. |

## Setup

### Prerequisites

- Python 3.10+
- A free [Spoonacular API key](https://spoonacular.com/food-api/console) (150 requests/day)

### Install

```bash
git clone <this-repo>
cd meal-planner-mcp
pip install -e .
```

Or with requirements directly:

```bash
pip install "mcp[cli]>=1.0.0" httpx pydantic
```

### Configure

Set your API key as an environment variable:

```bash
export SPOONACULAR_API_KEY="your_key_here"
```

### Run

```bash
# stdio transport (for Claude Desktop, Cursor, etc.)
python server.py

# or with fastmcp
fastmcp run server.py
```

## Demo

Run the included test client for a full 3-step walkthrough:

```bash
export SPOONACULAR_API_KEY="your_key_here"
python test_client.py
```

This will:
1. Search for "quick chicken dinner" recipes
2. Generate a grocery list for the first result
3. Estimate the total cost

Example output:

```
=== Step 1: suggest_meals('quick chicken dinner') ===
  [657579] Quick Chicken Enchilada Soup — 45 min
  [665261] Whole Chicken Dinner — 45 min
  [639657] Clear & Quick Chicken Soup — 45 min

=== Step 2: generate_grocery_list([657579]) ===
  Recipe: Quick Chicken Enchilada Soup
  Items:  9

=== Step 3: cost_estimate(9 ingredients) ===
  Estimated total: $23.31 USD
  Price-matched: 7/9 items
```

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "meal-planner": {
      "command": "python3",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "SPOONACULAR_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "meal-planner": {
      "command": "python3",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "SPOONACULAR_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add meal-planner -- python3 /absolute/path/to/server.py
```

## Price Table

`prices.json` contains 85+ common ingredient prices in USD. Ingredients not found in the table get a default price ($2.99). The matching is fuzzy — "chicken breast" matches "chicken" if no exact match exists. Edit the file to customize prices for your region.

## Data Sources

| Source | Auth | Coverage |
|--------|------|----------|
| **Spoonacular API** | API key (free tier) | 5,000+ recipes, nutritional data, ingredient breakdowns |
| **Local price table** | None | 85+ ingredients with USD prices, fully customizable |

## Caching & Rate Limits

- **In-memory cache**: 5-minute TTL per unique query. Identical requests cost 0 API points within the window.
- **Spoonacular free tier**: 150 points/day (~1 point per search). The server returns clear error messages when quota is exhausted.
- **Timeouts**: All HTTP requests have a 30-second timeout.
- **Response cap**: Grocery lists are truncated to 50 items if the response exceeds 25K characters.

## Limitations

- **Prices are estimates.** The local price table provides rough USD prices — not real-time store pricing.
- **Free API quota.** 150 points/day covers casual use. For heavier use, upgrade at [spoonacular.com](https://spoonacular.com/food-api/pricing).
- **No nutritional data.** The server focuses on recipes and costs. Spoonacular has nutrition endpoints but they are not exposed here.
