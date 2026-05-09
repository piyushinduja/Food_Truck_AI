"""Human-approved purchasing flow for inventory restocking."""
from __future__ import annotations

from datetime import datetime

from . import config
from .db import get_conn, init_db


def _default_supplier_id(conn) -> int | None:
    row = conn.execute("SELECT id FROM suppliers ORDER BY id ASC LIMIT 1").fetchone()
    return row["id"] if row else None


def estimate_restock_quantity(ingredient: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT ingredient, quantity, reorder_threshold, critical_threshold, expiration_date
            FROM inventory WHERE ingredient = ?
            """,
            (ingredient,),
        ).fetchone()
    if not row:
        return 0.0

    reorder = float(row["reorder_threshold"] or 0)
    critical = float(row["critical_threshold"] or 0)
    quantity = float(row["quantity"] or 0)
    expired = bool(row["expiration_date"] and row["expiration_date"] < datetime.utcnow().date().isoformat())

    base_target = max(reorder * 3, critical * 6, 1)
    if quantity <= 0 or expired:
        base_target = max(base_target, reorder * 4, 5)

    needed = max(base_target - quantity, 0)
    return round(needed, 2)


def estimate_restock_cost(ingredient: str, quantity: float) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT cost_per_unit FROM inventory WHERE ingredient = ?",
            (ingredient,),
        ).fetchone()
    if not row:
        return 0.0
    return round(float(row["cost_per_unit"]) * float(quantity) * 1.15, 2)


def get_restock_suggestions() -> list[dict]:
    init_db()
    from . import inventory as inventory_mod

    suggestions: list[dict] = []
    statuses = inventory_mod.get_inventory_status()

    with get_conn() as conn:
        supplier_lookup = {
            row["id"]: row["name"]
            for row in conn.execute("SELECT id, name FROM suppliers").fetchall()
        }

    for item in statuses:
        status = item["status"]
        if status not in {"low", "critical", "out", "expired", "expires_today", "expires_soon"}:
            continue
        needed = estimate_restock_quantity(item["ingredient"])
        if needed <= 0:
            continue
        urgency = "critical" if status in {"out", "expired", "critical"} else "normal"
        reason = {
            "low": "Below reorder threshold",
            "critical": "Below critical threshold",
            "out": "Out of stock",
            "expired": "Stock expired and unsafe",
            "expires_today": "Expires today",
            "expires_soon": "Expiring soon",
        }[status]
        supplier_name = supplier_lookup.get(item.get("supplier_id"))

        suggestions.append(
            {
                "ingredient": item["ingredient"],
                "current": item["quantity"],
                "unit": item["unit"],
                "status": status,
                "urgency": urgency,
                "reason": reason,
                "supplier_id": item.get("supplier_id"),
                "supplier_name": supplier_name,
                "estimated_qty": needed,
                "estimated_cost": estimate_restock_cost(item["ingredient"], needed),
            }
        )

    suggestions.sort(key=lambda x: (0 if x["urgency"] == "critical" else 1, x["ingredient"]))
    return suggestions


def create_purchase_order_from_suggestion(
    ingredient: str,
    quantity: float,
    supplier_id: int | None = None,
) -> dict:
    init_db()
    qty = float(quantity)
    if qty <= 0:
        return {"ok": False, "error": "quantity_must_be_positive"}

    with get_conn() as conn:
        inv = conn.execute(
            "SELECT ingredient, unit, cost_per_unit, supplier_id FROM inventory WHERE ingredient = ?",
            (ingredient,),
        ).fetchone()
        if not inv:
            return {"ok": False, "error": f"unknown_ingredient: {ingredient}"}

        supplier = supplier_id or inv["supplier_id"] or _default_supplier_id(conn)
        estimated_cost = estimate_restock_cost(ingredient, qty)

        cur = conn.execute(
            """
            INSERT INTO purchase_orders (supplier_id, status, estimated_total, notes)
            VALUES (?, 'suggested', ?, ?)
            """,
            (supplier, estimated_cost, f"Suggested restock for {ingredient}"),
        )
        po_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO purchase_order_items
            (purchase_order_id, ingredient, quantity, unit, estimated_cost)
            VALUES (?, ?, ?, ?, ?)
            """,
            (po_id, ingredient, qty, inv["unit"], estimated_cost),
        )

        conn.execute(
            """
            INSERT INTO agent_events (agent_name, severity, title, message, action_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Inventory + Supplies Purchasing Agent",
                "warning",
                "Purchase order drafted",
                f"PO #{po_id} drafted for {ingredient}: {qty} {inv['unit']}",
                "Review PO",
            ),
        )

    return {
        "ok": True,
        "purchase_order_id": po_id,
        "ingredient": ingredient,
        "quantity": qty,
        "estimated_cost": estimated_cost,
    }


def approve_purchase_order(purchase_order_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = ?",
            (purchase_order_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "purchase_order_not_found"}
        if row["status"] == "rejected":
            return {"ok": False, "error": "cannot_approve_rejected_order"}
        if row["status"] == "received":
            return {"ok": False, "error": "already_received"}
        conn.execute(
            """
            UPDATE purchase_orders
            SET status = 'approved', approved_at = COALESCE(approved_at, datetime('now'))
            WHERE id = ?
            """,
            (purchase_order_id,),
        )
    return {"ok": True, "purchase_order_id": purchase_order_id, "status": "approved"}


def reject_purchase_order(purchase_order_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = ?",
            (purchase_order_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "purchase_order_not_found"}
        if row["status"] == "received":
            return {"ok": False, "error": "cannot_reject_received_order"}
        conn.execute(
            "UPDATE purchase_orders SET status = 'rejected' WHERE id = ?",
            (purchase_order_id,),
        )
    return {"ok": True, "purchase_order_id": purchase_order_id, "status": "rejected"}


def mark_purchase_order_received(purchase_order_id: int) -> dict:
    init_db()
    with get_conn() as conn:
        po = conn.execute(
            "SELECT * FROM purchase_orders WHERE id = ?",
            (purchase_order_id,),
        ).fetchone()
        if not po:
            return {"ok": False, "error": "purchase_order_not_found"}
        if po["status"] == "rejected":
            return {"ok": False, "error": "cannot_receive_rejected_order"}
        if po["status"] == "received":
            return {"ok": False, "error": "already_received"}

        items = conn.execute(
            "SELECT * FROM purchase_order_items WHERE purchase_order_id = ?",
            (purchase_order_id,),
        ).fetchall()

        for item in items:
            conn.execute(
                "UPDATE inventory SET quantity = quantity + ? WHERE ingredient = ?",
                (item["quantity"], item["ingredient"]),
            )

            supplier = conn.execute(
                "SELECT name FROM suppliers WHERE id = ?",
                (po["supplier_id"],),
            ).fetchone()
            supplier_name = supplier["name"] if supplier else "supplier_mock"

            conn.execute(
                """
                INSERT INTO restock_log (ingredient, quantity, unit, cost, supplier, status)
                VALUES (?, ?, ?, ?, ?, 'delivered')
                """,
                (
                    item["ingredient"],
                    item["quantity"],
                    item["unit"],
                    item["estimated_cost"],
                    supplier_name,
                ),
            )

        conn.execute(
            """
            UPDATE purchase_orders
            SET status = 'received',
                approved_at = COALESCE(approved_at, datetime('now')),
                received_at = datetime('now')
            WHERE id = ?
            """,
            (purchase_order_id,),
        )

    from . import inventory as inventory_mod

    inventory_mod.recalculate_menu_availability()
    return {"ok": True, "purchase_order_id": purchase_order_id, "status": "received"}


def list_purchase_orders(status: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if status:
            po_rows = conn.execute(
                """
                SELECT po.*, s.name AS supplier_name
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                WHERE po.status = ?
                ORDER BY datetime(po.created_at) DESC
                """,
                (status,),
            ).fetchall()
        else:
            po_rows = conn.execute(
                """
                SELECT po.*, s.name AS supplier_name
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                ORDER BY datetime(po.created_at) DESC
                """
            ).fetchall()

        result = []
        for row in po_rows:
            items = conn.execute(
                "SELECT * FROM purchase_order_items WHERE purchase_order_id = ?",
                (row["id"],),
            ).fetchall()
            d = dict(row)
            d["items"] = [dict(i) for i in items]
            result.append(d)
    return result


def requires_human_approval() -> bool:
    return bool(config.get_config("requireHumanApprovalForPurchasing", True))
