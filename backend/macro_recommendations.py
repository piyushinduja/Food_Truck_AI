"""Deterministic macro-aware menu recommendation logic."""
from __future__ import annotations

from datetime import date, timedelta
from itertools import combinations_with_replacement

from . import macros, nutrition
from .autopilot import log_agent_event
from .db import get_conn, init_db


STRATEGIES = {
    "balanced",
    "high protein",
    "lower carb",
    "lower fat",
    "hit protein target",
    "stay under remaining macros",
    "use today remaining",
    "use yesterday missed",
}


def _remaining(customer_id: int, target_date: str) -> dict:
    summary = macros.get_daily_macro_summary(customer_id, target_date)
    return {
        "calories": max(0.0, float(summary.get("calories_remaining") or 0)),
        "protein_g": max(0.0, float(summary.get("protein_remaining_g") or 0)),
        "carbs_g": max(0.0, float(summary.get("carbs_remaining_g") or 0)),
        "fat_g": max(0.0, float(summary.get("fat_remaining_g") or 0)),
        "summary": summary,
    }


def _target_for_strategy(customer_id: int, target_date: str, strategy: str, scope: str) -> dict:
    remaining = _remaining(customer_id, target_date)
    target = {key: remaining[key] for key in ("calories", "protein_g", "carbs_g", "fat_g")}
    if scope == "meal":
        target = {key: value * 0.38 for key, value in target.items()}
    if strategy == "use yesterday missed":
        yesterday = get_yesterday_macro_context(customer_id)
        for key, missed_key in [
            ("calories", "calories_missed"),
            ("protein_g", "protein_missed_g"),
            ("carbs_g", "carbs_missed_g"),
            ("fat_g", "fat_missed_g"),
        ]:
            target[key] = max(target[key], float(yesterday.get(missed_key) or 0))
    if strategy == "high protein" or strategy == "hit protein target":
        target["protein_g"] *= 1.25
    if strategy == "lower carb":
        target["carbs_g"] *= 0.65
    if strategy == "lower fat":
        target["fat_g"] *= 0.65
    return target


def _combo_nutrition(combo: tuple[dict, ...]) -> dict:
    totals = {key: 0.0 for key in ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg")}
    for item in combo:
        for key in totals:
            totals[key] += float(item.get(key) or 0)
    for key in totals:
        totals[key] = round(totals[key], 2)
    totals["recommended_items"] = [
        {
            "menu_id": item["menu_item_id"],
            "name": item["name"],
            "price": item["price"],
            "category": item["category"],
            "quantity": 1,
        }
        for item in combo
    ]
    return totals


def _score(totals: dict, target: dict, strategy: str) -> float:
    calorie_unit = max(target.get("calories", 0), 600.0)
    protein_unit = max(target.get("protein_g", 0), 30.0)
    carb_unit = max(target.get("carbs_g", 0), 50.0)
    fat_unit = max(target.get("fat_g", 0), 20.0)

    score = abs(float(totals["calories"]) - target["calories"]) / calorie_unit
    score += abs(float(totals["protein_g"]) - target["protein_g"]) / protein_unit * 1.35
    score += abs(float(totals["carbs_g"]) - target["carbs_g"]) / carb_unit
    score += abs(float(totals["fat_g"]) - target["fat_g"]) / fat_unit

    if strategy in {"stay under remaining macros", "use today remaining"}:
        for key in ("calories", "carbs_g", "fat_g"):
            if float(totals[key]) > target[key]:
                score += ((float(totals[key]) - target[key]) / max(target[key], 1.0)) * 2.0
    if strategy in {"high protein", "hit protein target"}:
        score -= min(float(totals["protein_g"]) / protein_unit, 1.5) * 0.55
    if strategy == "lower carb":
        score += float(totals["carbs_g"]) / carb_unit * 0.45
    if strategy == "lower fat":
        score += float(totals["fat_g"]) / fat_unit * 0.45
    return round(score, 4)


def _rank_combinations(customer_id: int, target_date: str, strategy: str, scope: str, max_items: int) -> list[dict]:
    menu = nutrition.list_menu_with_nutrition(include_unavailable=False)
    target = _target_for_strategy(customer_id, target_date, strategy, scope)
    ranked: list[dict] = []

    for size in range(1, max_items + 1):
        for combo in combinations_with_replacement(menu, size):
            totals = _combo_nutrition(combo)
            totals["score"] = _score(totals, target, strategy)
            totals["target"] = target
            totals["strategy"] = strategy
            totals["scope"] = scope
            ranked.append(totals)

    ranked.sort(key=lambda row: row["score"])
    return ranked[:8]


def recommend_meal_for_macros(customer_id: int, target_date: str, strategy: str = "balanced") -> dict:
    strategy = strategy if strategy in STRATEGIES else "balanced"
    ranked = _rank_combinations(customer_id, target_date, strategy, "meal", max_items=3)
    best = ranked[0] if ranked else {}
    if best:
        log_agent_event("Customer Macro Agent", "healthy", "Meal recommendation generated", f"{strategy.title()} meal generated for customer #{customer_id}.", "Macro Meal")
    return {"ok": bool(best), "recommendation": best, "alternatives": ranked[1:4]}


def recommend_day_for_macros(customer_id: int, target_date: str, strategy: str = "balanced") -> dict:
    strategy = strategy if strategy in STRATEGIES else "balanced"
    ranked = _rank_combinations(customer_id, target_date, strategy, "day", max_items=6)
    best = ranked[0] if ranked else {}
    if best:
        items = best.get("recommended_items", [])
        groups = [
            {"label": "Meal 1", "items": items[0:2]},
            {"label": "Meal 2", "items": items[2:4]},
            {"label": "Meal 3", "items": items[4:6]},
        ]
        best["groups"] = [group for group in groups if group["items"]]
        target = best.get("target", {})
        best["can_satisfy_full_day"] = (
            abs(best["calories"] - target.get("calories", 0)) <= max(250, target.get("calories", 0) * 0.15)
            and abs(best["protein_g"] - target.get("protein_g", 0)) <= max(20, target.get("protein_g", 0) * 0.18)
        )
        log_agent_event("Customer Macro Agent", "healthy", "Full-day recommendation generated", f"{strategy.title()} day generated for customer #{customer_id}.", "Macro Day")
    return {"ok": bool(best), "recommendation": best, "alternatives": ranked[1:4]}


def rank_menu_items_for_remaining_macros(customer_id: int, target_date: str) -> list[dict]:
    target = _target_for_strategy(customer_id, target_date, "use today remaining", "meal")
    ranked = []
    for item in nutrition.list_menu_with_nutrition(include_unavailable=False):
        totals = {
            "calories": item["calories"],
            "protein_g": item["protein_g"],
            "carbs_g": item["carbs_g"],
            "fat_g": item["fat_g"],
        }
        item = dict(item)
        item["score"] = _score(totals, target, "use today remaining")
        ranked.append(item)
    ranked.sort(key=lambda row: row["score"])
    return ranked


def suggest_macro_swaps(cart_items: list[dict], customer_id: int, target_date: str) -> dict:
    current = nutrition.calculate_cart_nutrition(cart_items)
    ranked = rank_menu_items_for_remaining_macros(customer_id, target_date)
    current_ids = {int(item.get("menu_id") or 0) for item in cart_items}
    alternatives = [item for item in ranked if item["menu_item_id"] not in current_ids][:3]
    return {"current": current, "alternatives": alternatives}


def get_macro_gap_analysis(customer_id: int, target_date: str) -> dict:
    summary = macros.get_daily_macro_summary(customer_id, target_date)
    return {
        "summary": summary,
        "gaps": {
            "calories": float(summary.get("calories_remaining") or 0),
            "protein_g": float(summary.get("protein_remaining_g") or 0),
            "carbs_g": float(summary.get("carbs_remaining_g") or 0),
            "fat_g": float(summary.get("fat_remaining_g") or 0),
        },
    }


def get_yesterday_macro_context(customer_id: int) -> dict:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    summary = macros.get_daily_macro_summary(customer_id, yesterday)
    return {
        "date": yesterday,
        "summary": summary,
        "calories_missed": max(0.0, float(summary.get("calories_remaining") or 0)),
        "protein_missed_g": max(0.0, float(summary.get("protein_remaining_g") or 0)),
        "carbs_missed_g": max(0.0, float(summary.get("carbs_remaining_g") or 0)),
        "fat_missed_g": max(0.0, float(summary.get("fat_remaining_g") or 0)),
    }


def macro_owner_metrics(days: int = 30) -> dict:
    init_db()
    with get_conn() as conn:
        suggestion_count = conn.execute(
            "SELECT COUNT(*) AS c FROM macro_ai_suggestions WHERE date(created_at) >= date('now', ?)",
            (f"-{days} days",),
        ).fetchone()["c"]
        recommendation_events = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM agent_events
            WHERE agent_name = 'Customer Macro Agent'
              AND title IN ('Meal recommendation generated', 'Full-day recommendation generated')
              AND date(created_at) >= date('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()["c"]
        logged_orders = conn.execute(
            "SELECT COUNT(DISTINCT order_id) AS c FROM order_macro_logs WHERE order_id IS NOT NULL AND date(created_at) >= date('now', ?)",
            (f"-{days} days",),
        ).fetchone()["c"]
        avg_calories = conn.execute(
            "SELECT AVG(calories) AS v FROM order_macro_logs WHERE source = 'order' AND date(created_at) >= date('now', ?)",
            (f"-{days} days",),
        ).fetchone()["v"]
        strategy_counts = {}
        for strategy in sorted(STRATEGIES):
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM macro_ai_suggestions
                WHERE date(created_at) >= date('now', ?)
                  AND context LIKE ?
                """,
                (f"-{days} days", f"%{strategy}%"),
            ).fetchone()
            strategy_counts[strategy] = int(row["c"] if row else 0)
    ranked = rank_macro_friendly_items()
    top_strategy = max(strategy_counts.items(), key=lambda kv: kv[1])[0] if any(strategy_counts.values()) else None
    return {
        "macro_tracking_customers": macros.macro_customer_count(),
        "ai_suggestions_generated": int(suggestion_count or 0),
        "macro_recommendations_generated": int(recommendation_events or 0),
        "macro_logged_orders": int(logged_orders or 0),
        "recommendation_conversion_rate": round((float(logged_orders or 0) / float(recommendation_events or 1)) * 100, 1),
        "average_calories_per_macro_order": round(float(avg_calories or 0), 1),
        "most_macro_friendly_item": ranked[0]["name"] if ranked else None,
        "most_requested_macro_strategy": top_strategy,
    }


def rank_macro_friendly_items() -> list[dict]:
    items = []
    for item in nutrition.list_menu_with_nutrition(include_unavailable=False):
        item = dict(item)
        protein_density = float(item["protein_g"]) / max(float(item["calories"]), 1) * 100
        item["macro_friendliness_score"] = round(protein_density - (float(item["fat_g"]) * 0.08) - (float(item["sugar_g"]) * 0.04), 3)
        items.append(item)
    items.sort(key=lambda row: row["macro_friendliness_score"], reverse=True)
    return items
