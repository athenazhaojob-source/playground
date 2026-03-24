#!/usr/bin/env python3
"""
Minimal REPL client to exercise the Meal Planner MCP server.

Usage:
    python test_client.py

Requires SPOONACULAR_API_KEY in the environment.
"""

import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="python3",
        args=["server.py"],
        env={
            **os.environ,
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("=== Available Tools ===")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description[:80]}...")
            print()

            # Step 1: Suggest meals
            print("=== Step 1: suggest_meals('quick chicken dinner') ===")
            result = await session.call_tool(
                "suggest_meals",
                arguments={"query": "quick chicken dinner", "number": 3},
            )
            meals = json.loads(result.content[0].text)
            for m in meals:
                print(f"  [{m['id']}] {m['title']} — {m['readyInMinutes']} min")
            print()

            # Step 2: Generate grocery list from first recipe
            recipe_id = meals[0]["id"]
            print(f"=== Step 2: generate_grocery_list([{recipe_id}]) ===")
            result = await session.call_tool(
                "generate_grocery_list",
                arguments={"recipe_ids": [recipe_id]},
            )
            grocery = json.loads(result.content[0].text)
            print(f"  Recipe: {grocery['recipes'][0]}")
            print(f"  Items:  {grocery['total_items']}")
            for ing in grocery["ingredients"][:8]:
                print(f"    - {ing['amount']} {ing['unit']} {ing['name']}")
            if grocery["total_items"] > 8:
                print(f"    ... and {grocery['total_items'] - 8} more")
            print()

            # Step 3: Cost estimate
            names = [i["name"] for i in grocery["ingredients"]]
            print(f"=== Step 3: cost_estimate({len(names)} ingredients) ===")
            result = await session.call_tool(
                "cost_estimate",
                arguments={"ingredients": names},
            )
            cost = json.loads(result.content[0].text)
            print(f"  Estimated total: ${cost['total']:.2f} USD")
            matched = sum(1 for li in cost["line_items"] if li["matched"])
            print(f"  Price-matched: {matched}/{len(cost['line_items'])} items")
            print()

            # Step 4: Plan weekly meals
            print("=== Step 4: plan_weekly_meals(target_calories=2000) ===")
            result = await session.call_tool(
                "plan_weekly_meals",
                arguments={"target_calories": 2000},
            )
            plan = json.loads(result.content[0].text)
            print(f"  Target: {plan['target_calories']} cal/day")
            print(f"  Total recipes: {len(plan['all_recipe_ids'])}")
            monday = plan["week"]["monday"]
            print(f"  Monday meals:")
            for m in monday["meals"]:
                print(f"    - {m['title']} ({m['readyInMinutes']} min)")
            n = monday["nutrients"]
            print(f"  Monday nutrients: {n['calories']:.0f} cal, {n['protein']:.0f}g protein")
            print()

            print("Done! All four steps completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
