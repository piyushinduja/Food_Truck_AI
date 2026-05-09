"""Inventory operations.

deduct_for_order subtracts ingredients per the recipe.
get_low_stock returns items at or below their reorder threshold.
place_restock_order is a Walmart-style mock — pluggable later.
"""
import uuid
from .db import get_conn


def list_inventory():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM inventory ORDER BY ingredient"
        ).fetchall()
    return [dict(r) for r in rows]


def get_low_stock():
    """Items at or under their reorder threshold."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM inventory
               WHERE quantity <= reorder_threshold
               ORDER BY (quantity / NULLIF(reorder_threshold, 0)) ASC"""
        ).fetchall()
    return [dict(r) for r in rows]


def check_availability(menu_id: int, quantity: int) -> tuple[bool, list[str]]:
    """Can we make `quantity` servings of menu_id given current inventory?

    Returns (ok, missing) where missing is a list of ingredient names that
    would go negative.
    """
    with get_conn() as conn:
        recipe = conn.execute(
            """SELECT r.ingredient, r.qty_per_serving, i.quantity
               FROM recipe r JOIN inventory i ON r.ingredient = i.ingredient
               WHERE r.menu_id = ?""",
            (menu_id,),
        ).fetchall()

    missing = []
    for row in recipe:
        needed = row["qty_per_serving"] * quantity
        if row["quantity"] < needed:
            missing.append(row["ingredient"])
    return (len(missing) == 0, missing)


def deduct_for_order(order_id: int) -> dict:
    """Subtract ingredients for every line item in an order.

    Caller is responsible for having checked availability first; this
    will allow negative balances and return them in `went_negative` so
    the UI can flag a problem.
    """
    went_negative = []
    with get_conn() as conn:
        items = conn.execute(
            """SELECT oi.menu_id, oi.quantity, r.ingredient, r.qty_per_serving
               FROM order_items oi
               JOIN recipe r ON oi.menu_id = r.menu_id
               WHERE oi.order_id = ?""",
            (order_id,),
        ).fetchall()

        # Aggregate ingredient usage across all line items
        usage: dict[str, float] = {}
        for it in items:
            usage[it["ingredient"]] = usage.get(it["ingredient"], 0) + it["qty_per_serving"] * it["quantity"]

        for ingredient, qty in usage.items():
            conn.execute(
                "UPDATE inventory SET quantity = quantity - ? WHERE ingredient = ?",
                (qty, ingredient),
            )
            new_qty = conn.execute(
                "SELECT quantity FROM inventory WHERE ingredient = ?",
                (ingredient,),
            ).fetchone()["quantity"]
            if new_qty < 0:
                went_negative.append(ingredient)

    return {"deducted": usage, "went_negative": went_negative}


def place_restock_order(ingredient: str, quantity: float) -> dict:
    """Mock Walmart restock order.

    Adds quantity immediately (in real life this would be on delivery)
    and logs the order with a fake confirmation ID.
    """
    with get_conn() as conn:
        inv = conn.execute(
            "SELECT * FROM inventory WHERE ingredient = ?", (ingredient,)
        ).fetchone()
        if not inv:
            return {"ok": False, "error": f"unknown ingredient: {ingredient}"}

        cost = inv["cost_per_unit"] * quantity * 1.15  # 15% retail markup vs. internal cost
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ? WHERE ingredient = ?",
            (quantity, ingredient),
        )
        conn.execute(
            """INSERT INTO restock_log (ingredient, quantity, unit, cost, supplier, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ingredient, quantity, inv["unit"], cost, "walmart_mock", "delivered"),
        )

    return {
        "ok": True,
        "confirmation_id": f"WMT-{uuid.uuid4().hex[:8].upper()}",
        "ingredient": ingredient,
        "quantity": quantity,
        "unit": inv["unit"],
        "cost": round(cost, 2),
    }


def list_restocks(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM restock_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def predict_stockouts(days: int = 7) -> list[dict]:
    """Calculate consumption velocity and days-remaining for each ingredient.

    Returns list sorted by days_remaining ascending (most urgent first).
    Ingredients with zero velocity get days_remaining=None (no recent usage).
    """
    with get_conn() as conn:
        # Sum ingredient usage across all orders in the last N days
        usage_rows = conn.execute(
            """SELECT r.ingredient, SUM(oi.quantity * r.qty_per_serving) AS total_used
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.id
               JOIN recipe r ON oi.menu_id = r.menu_id
               WHERE o.created_at >= datetime('now', ? || ' days')
               GROUP BY r.ingredient""",
            (f"-{days}",),
        ).fetchall()

        inv_rows = conn.execute("SELECT * FROM inventory").fetchall()

    usage_map = {r["ingredient"]: r["total_used"] for r in usage_rows}

    result = []
    for inv in inv_rows:
        ing = inv["ingredient"]
        total_used = usage_map.get(ing, 0.0)
        daily_velocity = round(total_used / days, 4) if days > 0 else 0.0

        if daily_velocity > 0:
            days_remaining = round(inv["quantity"] / daily_velocity, 1)
        else:
            days_remaining = None  # not used recently

        result.append({
            "ingredient": ing,
            "current_qty": round(inv["quantity"], 2),
            "unit": inv["unit"],
            "daily_velocity": daily_velocity,
            "days_remaining": days_remaining,
            "reorder_threshold": inv["reorder_threshold"],
            "cost_per_unit": inv["cost_per_unit"],
        })

    # Sort: items with a days_remaining come first (most urgent), then None
    result.sort(key=lambda x: (x["days_remaining"] is None, x["days_remaining"] or 0))
    return result


def suggest_restocks() -> list[dict]:
    """For each low-stock item, suggest a quantity to bring it back to ~3x threshold."""
    suggestions = []
    for item in get_low_stock():
        target = max(item["reorder_threshold"] * 3, 1)
        needed = round(target - item["quantity"], 2)
        if needed > 0:
            suggestions.append({
                "ingredient": item["ingredient"],
                "current": item["quantity"],
                "suggested_qty": needed,
                "unit": item["unit"],
                "estimated_cost": round(item["cost_per_unit"] * needed * 1.15, 2),
            })
    return suggestions
