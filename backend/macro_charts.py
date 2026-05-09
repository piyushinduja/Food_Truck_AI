"""Chart-ready macro data helpers."""
from __future__ import annotations

from . import macros, nutrition


def get_macro_pie_data(customer_id: int, target_date: str) -> list[dict]:
    summary = macros.get_daily_macro_summary(customer_id, target_date)
    return [
        {"macro": "Protein", "grams": float(summary.get("protein_consumed_g") or 0), "calories": float(summary.get("protein_consumed_g") or 0) * 4},
        {"macro": "Carbs", "grams": float(summary.get("carbs_consumed_g") or 0), "calories": float(summary.get("carbs_consumed_g") or 0) * 4},
        {"macro": "Fat", "grams": float(summary.get("fat_consumed_g") or 0), "calories": float(summary.get("fat_consumed_g") or 0) * 9},
    ]


def get_macro_progress_data(customer_id: int, target_date: str) -> list[dict]:
    summary = macros.get_daily_macro_summary(customer_id, target_date)
    rows = [
        ("Calories", "calories_consumed", "calories_target", "calories_remaining"),
        ("Protein", "protein_consumed_g", "protein_target_g", "protein_remaining_g"),
        ("Carbs", "carbs_consumed_g", "carbs_target_g", "carbs_remaining_g"),
        ("Fat", "fat_consumed_g", "fat_target_g", "fat_remaining_g"),
    ]
    data = []
    for label, consumed_key, target_key, remaining_key in rows:
        consumed = float(summary.get(consumed_key) or 0)
        target = float(summary.get(target_key) or 0)
        pct = round((consumed / target) * 100, 1) if target > 0 else 0
        data.append(
            {
                "macro": label,
                "consumed": consumed,
                "target": target,
                "remaining": float(summary.get(remaining_key) or 0),
                "percent": pct,
                "status": "over" if target > 0 and consumed > target else "on_track",
            }
        )
    return data


def get_macro_history_chart_data(customer_id: int, days: int) -> list[dict]:
    return macros.get_macro_history(customer_id, days=days)


def get_order_macro_breakdown(order_id: int) -> dict:
    from . import orders

    order = orders.get_order(order_id)
    if not order:
        return {"ok": False, "error": "order_not_found"}
    totals = nutrition.estimate_order_nutrition(order.get("items", []))
    return {"ok": True, "order": order, "nutrition": totals}
