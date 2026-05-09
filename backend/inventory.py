"""Inventory operations with expiry-aware risk classification and purchasing integration."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from . import config
from .db import get_conn, init_db


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None


def list_inventory() -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM inventory ORDER BY ingredient").fetchall()
    return [dict(r) for r in rows]


def _classify_inventory_item(item: dict, warning_days: int) -> tuple[str, int | None]:
    today = date.today()
    exp = _parse_date(item.get("expiration_date"))
    days_to_expiry = (exp - today).days if exp else None

    qty = float(item.get("quantity") or 0)
    critical_threshold = float(item.get("critical_threshold") or 0)
    reorder_threshold = float(item.get("reorder_threshold") or 0)

    if exp and exp < today:
        return "expired", days_to_expiry
    if exp and exp == today:
        return "expires_today", days_to_expiry
    if exp and days_to_expiry is not None and days_to_expiry <= warning_days:
        return "expires_soon", days_to_expiry
    if qty <= 0:
        return "out", days_to_expiry
    if qty <= critical_threshold:
        return "critical", days_to_expiry
    if qty <= reorder_threshold:
        return "low", days_to_expiry
    return "ok", days_to_expiry


def get_inventory_status() -> list[dict]:
    warning_days = int(config.get_config("expiryWarningDays", 3) or 3)
    rows = list_inventory()
    status_rows: list[dict] = []
    for row in rows:
        status, days_to_expiry = _classify_inventory_item(row, warning_days)
        out = dict(row)
        out["status"] = status
        out["days_to_expiry"] = days_to_expiry
        status_rows.append(out)
    return status_rows


def get_expiring_inventory(days: int | None = None) -> list[dict]:
    warning_days = int(days if days is not None else config.get_config("expiryWarningDays", 3) or 3)
    rows = []
    for item in get_inventory_status():
        if item["status"] in {"expired", "expires_today", "expires_soon"}:
            if item["status"] == "expires_soon" and (item["days_to_expiry"] or 9999) > warning_days:
                continue
            rows.append(item)
    return rows


def get_inventory_alerts() -> list[dict]:
    alerts: list[dict] = []
    for item in get_inventory_status():
        if item["status"] == "ok":
            continue

        severity = "warning"
        if item["status"] in {"critical", "out", "expired"}:
            severity = "critical"

        alerts.append(
            {
                "ingredient": item["ingredient"],
                "status": item["status"],
                "severity": severity,
                "quantity": item["quantity"],
                "unit": item["unit"],
                "expiration_date": item.get("expiration_date"),
                "message": _inventory_alert_message(item),
            }
        )

    alerts.sort(key=lambda a: (0 if a["severity"] == "critical" else 1, a["ingredient"]))
    return alerts


def _inventory_alert_message(item: dict) -> str:
    status = item["status"]
    ingredient = item["ingredient"]
    qty = item["quantity"]
    unit = item["unit"]

    if status == "out":
        return f"{ingredient} is out ({qty} {unit})"
    if status == "critical":
        return f"{ingredient} is critical ({qty} {unit})"
    if status == "low":
        return f"{ingredient} is low ({qty} {unit})"
    if status == "expired":
        return f"{ingredient} is expired and unsafe"
    if status == "expires_today":
        return f"{ingredient} expires today"
    return f"{ingredient} expires soon"


def update_inventory_item(ingredient: str, **updates) -> dict:
    allowed = {
        "quantity",
        "unit",
        "reorder_threshold",
        "critical_threshold",
        "cost_per_unit",
        "expiration_date",
        "supplier_id",
        "category",
    }
    payload = {k: v for k, v in updates.items() if k in allowed}
    if not payload:
        return {"ok": False, "error": "no_valid_fields"}

    assignments = ", ".join(f"{k} = ?" for k in payload)
    values = list(payload.values()) + [ingredient]

    with get_conn() as conn:
        row = conn.execute(
            "SELECT ingredient FROM inventory WHERE ingredient = ?",
            (ingredient,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "ingredient_not_found"}
        conn.execute(
            f"UPDATE inventory SET {assignments} WHERE ingredient = ?",
            values,
        )

    recalculate_menu_availability()
    return {"ok": True, "ingredient": ingredient}


def mark_inventory_received(ingredient: str, quantity: float) -> dict:
    qty = float(quantity)
    if qty <= 0:
        return {"ok": False, "error": "quantity_must_be_positive"}

    with get_conn() as conn:
        inv = conn.execute(
            "SELECT ingredient, unit FROM inventory WHERE ingredient = ?",
            (ingredient,),
        ).fetchone()
        if not inv:
            return {"ok": False, "error": "ingredient_not_found"}
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ? WHERE ingredient = ?",
            (qty, ingredient),
        )

    recalculate_menu_availability()
    return {"ok": True, "ingredient": ingredient, "quantity_added": qty}


def recalculate_menu_availability() -> list[dict]:
    from . import menu as menu_mod

    return menu_mod.recalculate_menu_availability()


def get_unavailable_menu_items() -> list[dict]:
    today = date.today().isoformat()
    with get_conn() as conn:
        menu_rows = conn.execute(
            "SELECT id, name FROM menu WHERE available = 0 ORDER BY category, name"
        ).fetchall()

        result = []
        for row in menu_rows:
            blockers = conn.execute(
                """
                SELECT r.ingredient, i.quantity, i.expiration_date
                FROM recipe r
                JOIN inventory i ON i.ingredient = r.ingredient
                WHERE r.menu_id = ?
                  AND (i.quantity <= 0 OR (i.expiration_date IS NOT NULL AND i.expiration_date < ?))
                """,
                (row["id"], today),
            ).fetchall()

            result.append(
                {
                    "menu_id": row["id"],
                    "menu_name": row["name"],
                    "blocking_ingredients": [dict(b) for b in blockers],
                }
            )
    return result


def get_low_stock() -> list[dict]:
    return [
        item
        for item in get_inventory_status()
        if item["status"] in {"low", "critical", "out"}
    ]


def check_availability(menu_id: int, quantity: int) -> tuple[bool, list[str]]:
    with get_conn() as conn:
        recipe = conn.execute(
            """
            SELECT r.ingredient, r.qty_per_serving, i.quantity, i.expiration_date
            FROM recipe r
            JOIN inventory i ON r.ingredient = i.ingredient
            WHERE r.menu_id = ?
            """,
            (menu_id,),
        ).fetchall()

    today = date.today().isoformat()
    missing = []
    for row in recipe:
        needed = row["qty_per_serving"] * quantity
        is_expired = bool(row["expiration_date"] and row["expiration_date"] < today)
        if row["quantity"] < needed or is_expired:
            missing.append(row["ingredient"])
    return (len(missing) == 0, missing)


def deduct_for_order(order_id: int) -> dict:
    went_negative = []
    with get_conn() as conn:
        items = conn.execute(
            """
            SELECT oi.menu_id, oi.quantity, r.ingredient, r.qty_per_serving
            FROM order_items oi
            JOIN recipe r ON oi.menu_id = r.menu_id
            WHERE oi.order_id = ?
            """,
            (order_id,),
        ).fetchall()

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

    recalculate_menu_availability()
    return {"deducted": usage, "went_negative": went_negative}


def place_restock_order(ingredient: str, quantity: float) -> dict:
    """Compatibility wrapper: drafts PO and optionally auto-receives if approval disabled."""
    from . import purchasing

    created = purchasing.create_purchase_order_from_suggestion(ingredient, quantity)
    if not created.get("ok"):
        return created

    po_id = created["purchase_order_id"]
    if purchasing.requires_human_approval():
        return {
            "ok": True,
            "mode": "approval_required",
            "purchase_order_id": po_id,
            "message": "Purchase order drafted. Approval required before receiving inventory.",
            "confirmation_id": f"PO-{po_id:04d}",
            "ingredient": ingredient,
            "quantity": quantity,
            "cost": created["estimated_cost"],
        }

    purchasing.approve_purchase_order(po_id)
    purchasing.mark_purchase_order_received(po_id)
    return {
        "ok": True,
        "mode": "auto_received",
        "purchase_order_id": po_id,
        "confirmation_id": f"WMT-{uuid.uuid4().hex[:8].upper()}",
        "ingredient": ingredient,
        "quantity": quantity,
        "cost": created["estimated_cost"],
    }


def list_restocks(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM restock_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
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
    from . import purchasing

    suggestions = purchasing.get_restock_suggestions()
    return [
        {
            "ingredient": s["ingredient"],
            "current": s["current"],
            "suggested_qty": s["estimated_qty"],
            "unit": s["unit"],
            "estimated_cost": s["estimated_cost"],
            "urgency": s["urgency"],
            "reason": s["reason"],
        }
        for s in suggestions
    ]
