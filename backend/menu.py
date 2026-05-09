"""Menu CRUD and availability calculations."""
from __future__ import annotations

from datetime import date

from .db import get_conn, init_db


def list_menu(include_unavailable: bool = True) -> list[dict]:
    init_db()
    with get_conn() as conn:
        query = "SELECT * FROM menu"
        params: tuple = ()
        if not include_unavailable:
            query += " WHERE available = 1"
        query += " ORDER BY sort_order ASC, category ASC, name ASC"
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_menu_item(menu_id: int, **updates) -> dict:
    allowed = {
        "name",
        "price",
        "category",
        "description",
        "available",
        "prep_time_minutes",
        "cook_time_minutes",
        "image_url",
        "sort_order",
    }
    payload = {k: v for k, v in updates.items() if k in allowed}
    if not payload:
        return {"ok": False, "error": "no_valid_fields"}

    sets = ", ".join(f"{key} = ?" for key in payload)
    values = list(payload.values()) + [menu_id]

    init_db()
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM menu WHERE id = ?", (menu_id,)).fetchone()
        if not exists:
            return {"ok": False, "error": "menu_not_found"}
        conn.execute(f"UPDATE menu SET {sets} WHERE id = ?", values)
    return {"ok": True, "menu_id": menu_id}


def update_menu_timing(menu_id: int, prep_time_minutes: float, cook_time_minutes: float) -> dict:
    prep = max(float(prep_time_minutes), 0)
    cook = max(float(cook_time_minutes), 0)
    return update_menu_item(menu_id, prep_time_minutes=prep, cook_time_minutes=cook)


def recalculate_menu_availability() -> list[dict]:
    """Recompute menu.available based on ingredient stock and expiry safety."""
    today = date.today().isoformat()
    init_db()
    unavailable: list[dict] = []

    with get_conn() as conn:
        menu_rows = conn.execute("SELECT id, name FROM menu").fetchall()
        for row in menu_rows:
            menu_id = row["id"]
            recipe_rows = conn.execute(
                """
                SELECT r.ingredient, r.qty_per_serving, i.quantity, i.expiration_date
                FROM recipe r
                JOIN inventory i ON i.ingredient = r.ingredient
                WHERE r.menu_id = ?
                """,
                (menu_id,),
            ).fetchall()

            item_available = 1
            missing_or_unsafe: list[str] = []
            for rec in recipe_rows:
                is_expired = bool(rec["expiration_date"] and rec["expiration_date"] < today)
                if rec["quantity"] <= 0 or is_expired:
                    item_available = 0
                    missing_or_unsafe.append(rec["ingredient"])

            conn.execute(
                "UPDATE menu SET available = ? WHERE id = ?",
                (item_available, menu_id),
            )
            if not item_available:
                unavailable.append(
                    {
                        "menu_id": menu_id,
                        "menu_name": row["name"],
                        "blocking_ingredients": missing_or_unsafe,
                    }
                )

    return unavailable
