"""Menu nutrition storage and deterministic nutrition calculations."""
from __future__ import annotations

from typing import Any

from .db import get_conn, init_db


MACRO_KEYS = ("calories", "protein_g", "carbs_g", "fat_g")
OPTIONAL_KEYS = ("fiber_g", "sugar_g", "sodium_mg")


def _zero_totals() -> dict[str, float]:
    return {key: 0.0 for key in (*MACRO_KEYS, *OPTIONAL_KEYS)}


def get_menu_nutrition(menu_item_id: int) -> dict | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT mn.*, m.name, m.category, m.price, m.available
            FROM menu_nutrition mn
            JOIN menu m ON m.id = mn.menu_item_id
            WHERE mn.menu_item_id = ?
            """,
            (menu_item_id,),
        ).fetchone()
    return dict(row) if row else None


def list_menu_with_nutrition(include_unavailable: bool = False) -> list[dict]:
    init_db()
    where = "" if include_unavailable else "WHERE m.available = 1"
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
                m.id AS menu_item_id,
                m.name,
                m.category,
                m.description,
                m.price,
                m.available,
                m.sort_order,
                mn.calories,
                mn.protein_g,
                mn.carbs_g,
                mn.fat_g,
                COALESCE(mn.fiber_g, 0) AS fiber_g,
                COALESCE(mn.sugar_g, 0) AS sugar_g,
                COALESCE(mn.sodium_mg, 0) AS sodium_mg,
                mn.source,
                mn.updated_at
            FROM menu m
            JOIN menu_nutrition mn ON mn.menu_item_id = m.id
            {where}
            ORDER BY m.sort_order ASC, m.category ASC, m.name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def update_menu_nutrition(menu_item_id: int, nutrition_data: dict[str, Any]) -> dict:
    payload = {
        key: float(nutrition_data.get(key, 0) or 0)
        for key in (*MACRO_KEYS, *OPTIONAL_KEYS)
        if key in nutrition_data
    }
    if not all(key in payload for key in MACRO_KEYS):
        existing = get_menu_nutrition(menu_item_id) or {}
        for key in MACRO_KEYS:
            payload.setdefault(key, float(existing.get(key, 0) or 0))
    for key in OPTIONAL_KEYS:
        payload.setdefault(key, float(nutrition_data.get(key, 0) or 0))
    source = str(nutrition_data.get("source") or "owner_edit")

    init_db()
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM menu WHERE id = ?", (menu_item_id,)).fetchone()
        if not exists:
            return {"ok": False, "error": "menu_not_found"}
        conn.execute(
            """
            INSERT INTO menu_nutrition (
                menu_item_id, calories, protein_g, carbs_g, fat_g,
                fiber_g, sugar_g, sodium_mg, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(menu_item_id) DO UPDATE SET
                calories = excluded.calories,
                protein_g = excluded.protein_g,
                carbs_g = excluded.carbs_g,
                fat_g = excluded.fat_g,
                fiber_g = excluded.fiber_g,
                sugar_g = excluded.sugar_g,
                sodium_mg = excluded.sodium_mg,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                menu_item_id,
                payload["calories"],
                payload["protein_g"],
                payload["carbs_g"],
                payload["fat_g"],
                payload["fiber_g"],
                payload["sugar_g"],
                payload["sodium_mg"],
                source,
            ),
        )
    return {"ok": True, "menu_item_id": menu_item_id}


def calculate_cart_nutrition(cart_items: list[dict]) -> dict:
    totals = _zero_totals()
    line_items: list[dict] = []

    for item in cart_items:
        menu_id = int(item.get("menu_id") or 0)
        qty = max(1, int(item.get("quantity") or 1))
        nutrition = get_menu_nutrition(menu_id)
        if not nutrition:
            line_items.append(
                {
                    "menu_id": menu_id,
                    "name": item.get("name") or f"Menu #{menu_id}",
                    "quantity": qty,
                    "missing_nutrition": True,
                }
            )
            continue

        line = {
            "menu_id": menu_id,
            "name": nutrition["name"],
            "quantity": qty,
            "missing_nutrition": False,
        }
        for key in (*MACRO_KEYS, *OPTIONAL_KEYS):
            value = round(float(nutrition.get(key) or 0) * qty, 2)
            line[key] = value
            totals[key] += value
        line_items.append(line)

    for key in totals:
        totals[key] = round(totals[key], 2)
    totals["items"] = line_items
    totals["missing_nutrition_items"] = [line for line in line_items if line.get("missing_nutrition")]
    return totals


def estimate_order_nutrition(order_items: list[dict]) -> dict:
    cart_items = [
        {
            "menu_id": item.get("menu_id"),
            "name": item.get("item_name") or item.get("name"),
            "quantity": item.get("quantity", 1),
        }
        for item in order_items
    ]
    return calculate_cart_nutrition(cart_items)


def validate_menu_nutrition_exists() -> bool:
    return not get_missing_nutrition_items()


def get_missing_nutrition_items() -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.name, m.category
            FROM menu m
            LEFT JOIN menu_nutrition mn ON mn.menu_item_id = m.id
            WHERE mn.id IS NULL
            ORDER BY m.sort_order ASC, m.name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]
