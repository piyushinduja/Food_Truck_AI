"""Order lifecycle and deterministic order processing."""
from __future__ import annotations

from datetime import datetime

from . import inventory as inv_mod
from . import kitchen as kitchen_mod
from . import menu as menu_mod
from . import payments
from .db import get_conn, init_db


STATUS_FLOW = ["pending", "preparing", "ready", "completed"]


def get_menu(only_available: bool = True) -> list[dict]:
    return menu_mod.list_menu(include_unavailable=not only_available)


def _next_order_number(conn) -> str:
    row = conn.execute(
        """
        SELECT order_number
        FROM orders
        WHERE order_number LIKE 'EC-%'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    next_num = 1001
    if row and row["order_number"]:
        try:
            next_num = int(row["order_number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_num = 1001

    return f"EC-{next_num:04d}"


def create_order(
    cart: list[dict],
    customer_name: str = "guest",
    source: str = "kiosk",
    customer_id: int | None = None,
    track_macros: bool = False,
) -> dict:
    """Create a paid order, deduct inventory, and generate kitchen timeline."""
    init_db()
    if not cart:
        return {"ok": False, "error": "empty_cart"}

    with get_conn() as conn:
        menu_rows = {
            row["id"]: dict(row)
            for row in conn.execute("SELECT * FROM menu").fetchall()
        }

    total = 0.0
    for item in cart:
        qty = int(item.get("quantity") or 0)
        if qty <= 0:
            return {"ok": False, "error": "invalid_quantity"}

        m = menu_rows.get(item["menu_id"])
        if not m:
            return {"ok": False, "error": f"unknown_menu_item:{item['menu_id']}"}
        if not m["available"]:
            return {"ok": False, "error": f"unavailable:{m['name']}"}

        ok, missing = inv_mod.check_availability(item["menu_id"], qty)
        if not ok:
            return {
                "ok": False,
                "error": f"out_of_stock:{m['name']}",
                "missing_ingredients": missing,
            }
        total += float(m["price"]) * qty

    pay = payments.charge(total, customer_name)
    if pay["status"] != "succeeded":
        return {"ok": False, "error": "payment_failed", "details": pay}

    with get_conn() as conn:
        order_number = _next_order_number(conn)
        cur = conn.execute(
            """
            INSERT INTO orders (
                order_number,
                customer_name,
                status,
                total,
                payment_status,
                payment_id,
                source
            ) VALUES (?, ?, 'pending', ?, 'paid', ?, ?)
            """,
            (order_number, customer_name, round(total, 2), pay["payment_id"], source),
        )
        order_id = cur.lastrowid

        for item in cart:
            m = menu_rows[item["menu_id"]]
            conn.execute(
                """
                INSERT INTO order_items (order_id, menu_id, quantity, unit_price, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["menu_id"],
                    int(item["quantity"]),
                    float(m["price"]),
                    item.get("notes"),
                ),
            )

    deduction = inv_mod.deduct_for_order(order_id)
    kitchen_mod.save_kitchen_timeline(order_id)
    eta = kitchen_mod.estimate_ready_time(order_id)
    macro_log = None
    if track_macros and customer_id:
        from . import macros as macros_mod

        macro_log = macros_mod.log_order_macros(customer_id, order_id)

    return {
        "ok": True,
        "order_id": order_id,
        "order_number": order_number,
        "total": round(total, 2),
        "payment_id": pay["payment_id"],
        "deduction": deduction,
        "estimated_ready_at": eta["estimated_ready_at"] if eta else None,
        "estimated_wait_minutes": eta["estimated_wait_minutes"] if eta else None,
        "macro_log": macro_log,
    }


def _order_items(conn, order_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT oi.*, m.name AS item_name
        FROM order_items oi
        JOIN menu m ON oi.menu_id = m.id
        WHERE oi.order_id = ?
        ORDER BY oi.id ASC
        """,
        (order_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_orders(status: str | None = None, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        if status:
            order_rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE status = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        else:
            order_rows = conn.execute(
                """
                SELECT * FROM orders
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = []
        for row in order_rows:
            d = dict(row)
            d["items"] = _order_items(conn, d["id"])
            result.append(d)
    return result


def list_active_orders() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE status IN ('pending', 'preparing', 'ready')
            ORDER BY datetime(created_at) ASC
            """
        ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["items"] = _order_items(conn, d["id"])
            result.append(d)
    return result


def get_order(order_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = _order_items(conn, order_id)
    return d


def get_order_by_number(order_number: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_number = ?",
            (order_number,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = _order_items(conn, d["id"])
    return d


def advance_status(order_id: int) -> dict:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}

        status = row["status"]
        if status not in STATUS_FLOW:
            return {"ok": False, "error": "bad_status"}

        next_idx = STATUS_FLOW.index(status) + 1
        if next_idx >= len(STATUS_FLOW):
            return {"ok": False, "error": "already_completed"}

        new_status = STATUS_FLOW[next_idx]
        conn.execute(
            """
            UPDATE orders
            SET status = ?,
                kitchen_started_at = CASE WHEN ? = 'preparing' THEN COALESCE(kitchen_started_at, ?) ELSE kitchen_started_at END,
                ready_at = CASE WHEN ? = 'ready' THEN COALESCE(ready_at, ?) ELSE ready_at END,
                completed_at = CASE WHEN ? = 'completed' THEN COALESCE(completed_at, ?) ELSE completed_at END
            WHERE id = ?
            """,
            (new_status, new_status, now, new_status, now, new_status, now, order_id),
        )

    return {"ok": True, "order_id": order_id, "new_status": new_status}


def cancel_order(order_id: int) -> dict:
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not exists:
            return {"ok": False, "error": "not_found"}
        conn.execute(
            """
            UPDATE orders
            SET status = 'cancelled',
                completed_at = COALESCE(completed_at, datetime('now'))
            WHERE id = ?
            """,
            (order_id,),
        )
    return {"ok": True, "order_id": order_id, "new_status": "cancelled"}
