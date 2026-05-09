"""Order lifecycle: create, list active, advance status, complete."""
from datetime import datetime
from .db import get_conn
from . import inventory as inv_mod
from . import payments


STATUS_FLOW = ["pending", "preparing", "ready", "completed"]


def get_menu(only_available: bool = True):
    with get_conn() as conn:
        q = "SELECT * FROM menu"
        if only_available:
            q += " WHERE available = 1"
        q += " ORDER BY category, name"
        rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def create_order(cart: list[dict], customer_name: str = "guest", phone: str | None = None) -> dict:
    """cart: [{menu_id, quantity, notes?}, ...]

    Validates availability, charges payment, creates order rows, deducts inventory.
    Returns {ok, order_id?, error?, ...}.
    """
    if not cart:
        return {"ok": False, "error": "empty_cart"}

    # 1. Look up prices and validate availability
    with get_conn() as conn:
        menu_rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM menu").fetchall()}

    total = 0.0
    for item in cart:
        m = menu_rows.get(item["menu_id"])
        if not m:
            return {"ok": False, "error": f"unknown menu item: {item['menu_id']}"}
        if not m["available"]:
            return {"ok": False, "error": f"unavailable: {m['name']}"}
        ok, missing = inv_mod.check_availability(item["menu_id"], item["quantity"])
        if not ok:
            return {
                "ok": False,
                "error": f"out_of_stock: {m['name']}",
                "missing_ingredients": missing,
            }
        total += m["price"] * item["quantity"]

    # 2. Charge payment
    pay = payments.charge(total, customer_name)
    if pay["status"] != "succeeded":
        return {"ok": False, "error": "payment_failed", "details": pay}

    # 3. Insert order + items
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders (customer_name, phone, status, total, payment_status, payment_id)
               VALUES (?, ?, 'pending', ?, 'paid', ?)""",
            (customer_name, phone, total, pay["payment_id"]),
        )
        order_id = cur.lastrowid
        for item in cart:
            m = menu_rows[item["menu_id"]]
            conn.execute(
                """INSERT INTO order_items (order_id, menu_id, quantity, unit_price, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, item["menu_id"], item["quantity"], m["price"], item.get("notes")),
            )

    # 4. Deduct inventory
    deduction = inv_mod.deduct_for_order(order_id)

    return {
        "ok": True,
        "order_id": order_id,
        "total": round(total, 2),
        "payment_id": pay["payment_id"],
        "deduction": deduction,
    }


def list_orders(status: str | None = None, limit: int = 50):
    with get_conn() as conn:
        if status:
            order_rows = conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            order_rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

        result = []
        for o in order_rows:
            items = conn.execute(
                """SELECT oi.*, m.name AS item_name
                   FROM order_items oi JOIN menu m ON oi.menu_id = m.id
                   WHERE oi.order_id = ?""",
                (o["id"],),
            ).fetchall()
            d = dict(o)
            d["items"] = [dict(i) for i in items]
            result.append(d)
    return result


def list_active_orders():
    """Pending, preparing, or ready — anything not completed."""
    with get_conn() as conn:
        order_rows = conn.execute(
            """SELECT * FROM orders
               WHERE status IN ('pending', 'preparing', 'ready')
               ORDER BY created_at ASC"""
        ).fetchall()
        result = []
        for o in order_rows:
            items = conn.execute(
                """SELECT oi.*, m.name AS item_name
                   FROM order_items oi JOIN menu m ON oi.menu_id = m.id
                   WHERE oi.order_id = ?""",
                (o["id"],),
            ).fetchall()
            d = dict(o)
            d["items"] = [dict(i) for i in items]
            result.append(d)
    return result


def advance_status(order_id: int) -> dict:
    """Move order to next stage in STATUS_FLOW."""
    phone = None
    customer_name = None
    new_status = None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, customer_name, phone FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}
        try:
            next_idx = STATUS_FLOW.index(row["status"]) + 1
        except ValueError:
            return {"ok": False, "error": "bad_status"}
        if next_idx >= len(STATUS_FLOW):
            return {"ok": False, "error": "already_completed"}
        new_status = STATUS_FLOW[next_idx]
        completed_at = datetime.utcnow().isoformat() if new_status == "completed" else None
        conn.execute(
            "UPDATE orders SET status = ?, completed_at = COALESCE(?, completed_at) WHERE id = ?",
            (new_status, completed_at, order_id),
        )
        if new_status == "ready":
            phone = row["phone"]
            customer_name = row["customer_name"]

    if new_status == "ready" and phone:
        from . import sms as sms_mod
        sms_mod.send_sms(phone, f"Hey {customer_name}! Your order #{order_id} at El Camino is ready for pickup. 🌮")

    return {"ok": True, "order_id": order_id, "new_status": new_status}


def cancel_order(order_id: int) -> dict:
    """Mark as completed (refund flow would go here in real life)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (order_id,),
        )
    return {"ok": True, "order_id": order_id}
