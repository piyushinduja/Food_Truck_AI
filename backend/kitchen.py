"""Kitchen timing engine and queue helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import config
from .db import get_conn, init_db
from .timing import estimate_menu_timing, has_placeholder_timing


ACTIVE_STATUSES = ("pending", "preparing", "ready")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def get_order_with_timing_data(order_id: int) -> dict | None:
    init_db()
    with get_conn() as conn:
        order_row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order_row:
            return None

        items = conn.execute(
            """
            SELECT
                oi.id AS order_item_id,
                oi.menu_id,
                oi.quantity,
                oi.notes,
                m.name AS item_name,
                m.category,
                m.description,
                COALESCE(m.prep_time_minutes, 1) AS prep_time_minutes,
                COALESCE(m.cook_time_minutes, 5) AS cook_time_minutes
            FROM order_items oi
            JOIN menu m ON m.id = oi.menu_id
            WHERE oi.order_id = ?
            ORDER BY oi.id ASC
            """,
            (order_id,),
        ).fetchall()

    order = dict(order_row)
    normalized_items = []
    for item in items:
        d = dict(item)
        if has_placeholder_timing(d):
            prep, cook = estimate_menu_timing(
                {
                    "name": d.get("item_name"),
                    "category": d.get("category"),
                    "description": d.get("description"),
                }
            )
            d["prep_time_minutes"] = prep
            d["cook_time_minutes"] = cook
        per_serving = float(d["prep_time_minutes"]) + float(d["cook_time_minutes"])
        # Prototype quantity scaling: each extra unit adds 60% of full cycle.
        qty = max(int(d["quantity"]), 1)
        total_minutes = per_serving + max(0, qty - 1) * (per_serving * 0.6)
        d["total_minutes"] = round(total_minutes, 2)
        normalized_items.append(d)

    order["items"] = normalized_items
    order["created_at_dt"] = _parse_dt(order.get("created_at"))
    return order


def generate_kitchen_timeline(order_id: int) -> list[dict]:
    order = get_order_with_timing_data(order_id)
    if not order or not order["items"]:
        return []

    longest = max(item["total_minutes"] for item in order["items"])
    start_base = order["created_at_dt"]
    timeline = []

    for item in order["items"]:
        duration = float(item["total_minutes"])
        start_offset = max(0.0, round(longest - duration, 2))
        target_start = start_base + timedelta(minutes=start_offset)
        target_finish = target_start + timedelta(minutes=duration)
        verb = "Prep" if float(item.get("cook_time_minutes") or 0) <= 0 else "Cook"

        timeline.append(
            {
                "order_id": order_id,
                "order_item_id": item["order_item_id"],
                "item_name": item["item_name"],
                "action": f"{verb} {item['quantity']}x {item['item_name']}",
                "start_offset_minutes": start_offset,
                "duration_minutes": round(duration, 2),
                "target_start_time": target_start.strftime("%Y-%m-%d %H:%M:%S"),
                "target_finish_time": target_finish.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "pending",
                "urgency": "high" if start_offset == 0 else "normal",
            }
        )

    return timeline


def estimate_ready_time(order_id: int) -> dict | None:
    order = get_order_with_timing_data(order_id)
    if not order or not order["items"]:
        return None

    longest = max(item["total_minutes"] for item in order["items"])
    business_cfg = config.get_business_config()
    buffer = float(business_cfg.get("defaultPrepBufferMinutes", 0) or 0)

    created_at = order["created_at_dt"]
    ready_at = created_at + timedelta(minutes=(longest + buffer))
    wait_minutes = max(0.0, round((ready_at - created_at).total_seconds() / 60, 1))

    return {
        "estimated_ready_at": ready_at.strftime("%Y-%m-%d %H:%M:%S"),
        "estimated_wait_minutes": wait_minutes,
    }


def save_kitchen_timeline(order_id: int) -> list[dict]:
    timeline = generate_kitchen_timeline(order_id)
    eta = estimate_ready_time(order_id)

    with get_conn() as conn:
        conn.execute("DELETE FROM kitchen_timeline_steps WHERE order_id = ?", (order_id,))

        for step in timeline:
            conn.execute(
                """
                INSERT INTO kitchen_timeline_steps (
                    order_id,
                    order_item_id,
                    item_name,
                    action,
                    start_offset_minutes,
                    duration_minutes,
                    target_start_time,
                    target_finish_time,
                    status,
                    urgency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step["order_id"],
                    step["order_item_id"],
                    step["item_name"],
                    step["action"],
                    step["start_offset_minutes"],
                    step["duration_minutes"],
                    step["target_start_time"],
                    step["target_finish_time"],
                    step["status"],
                    step["urgency"],
                ),
            )

        if eta:
            conn.execute(
                "UPDATE orders SET estimated_ready_at = ? WHERE id = ?",
                (eta["estimated_ready_at"], order_id),
            )

    return timeline


def get_kitchen_timeline(order_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM kitchen_timeline_steps
            WHERE order_id = ?
            ORDER BY start_offset_minutes ASC, id ASC
            """,
            (order_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_kitchen_orders() -> list[dict]:
    now = datetime.utcnow()
    orders: list[dict] = []

    with get_conn() as conn:
        order_rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE status IN ('pending', 'preparing', 'ready')
            ORDER BY datetime(created_at) ASC
            """
        ).fetchall()

        for row in order_rows:
            order = dict(row)
            items = conn.execute(
                """
                SELECT oi.*, m.name AS item_name
                FROM order_items oi
                JOIN menu m ON m.id = oi.menu_id
                WHERE oi.order_id = ?
                ORDER BY oi.id ASC
                """,
                (order["id"],),
            ).fetchall()
            steps = conn.execute(
                """
                SELECT * FROM kitchen_timeline_steps
                WHERE order_id = ?
                ORDER BY start_offset_minutes ASC
                """,
                (order["id"],),
            ).fetchall()

            created_at = _parse_dt(order.get("created_at"))
            estimated_ready = _parse_dt(order.get("estimated_ready_at")) if order.get("estimated_ready_at") else None
            elapsed_minutes = round((now - created_at).total_seconds() / 60, 1)
            remaining_minutes = None
            is_late = False
            if estimated_ready:
                remaining_minutes = round((estimated_ready - now).total_seconds() / 60, 1)
                is_late = remaining_minutes < 0 and order.get("status") != "ready"

            order["items"] = [dict(i) for i in items]
            order["timeline"] = [dict(s) for s in steps]
            order["elapsed_minutes"] = max(elapsed_minutes, 0.0)
            order["remaining_minutes"] = remaining_minutes
            order["is_late"] = is_late

            # Convert UTC estimated_ready_at to local time for display
            eta_display = None
            if order.get("estimated_ready_at"):
                try:
                    utc_dt = datetime.strptime(order["estimated_ready_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    local_dt = utc_dt.astimezone()
                    hour = local_dt.hour % 12 or 12
                    ampm = "AM" if local_dt.hour < 12 else "PM"
                    eta_display = f"{hour}:{local_dt.strftime('%M')} {ampm}"
                except (ValueError, AttributeError):
                    eta_display = order["estimated_ready_at"]
            order["estimated_ready_at_display"] = eta_display

            orders.append(order)

    return orders


def mark_timeline_step_status(step_id: int, status: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT order_id FROM kitchen_timeline_steps WHERE id = ?",
            (step_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "step_not_found"}
        conn.execute(
            "UPDATE kitchen_timeline_steps SET status = ? WHERE id = ?",
            (status, step_id),
        )
    return {"ok": True, "step_id": step_id, "status": status}
