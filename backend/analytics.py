"""Deterministic analytics queries for sales, costs, profit, and risk."""
from __future__ import annotations

from datetime import date, timedelta

from .db import get_conn
from . import inventory as inventory_mod


def _since_date(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def sales_by_item(days: int = 7) -> list[dict]:
    since = _since_date(days)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.name, m.category,
                   SUM(oi.quantity) AS units_sold,
                   SUM(oi.quantity * oi.unit_price) AS revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN menu m ON oi.menu_id = m.id
            WHERE date(o.created_at) >= ?
              AND o.status != 'cancelled'
            GROUP BY m.id
            ORDER BY units_sold DESC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def revenue_by_day(days: int = 30) -> list[dict]:
    since = _since_date(days)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date(created_at) AS day,
                   COUNT(*) AS num_orders,
                   SUM(total) AS revenue
            FROM orders
            WHERE date(created_at) >= ?
              AND status != 'cancelled'
            GROUP BY date(created_at)
            ORDER BY day ASC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def today_summary() -> dict:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS num_orders,
                   COALESCE(SUM(total), 0) AS revenue,
                   COALESCE(AVG(total), 0) AS avg_ticket
            FROM orders
            WHERE date(created_at) = ?
              AND status != 'cancelled'
            """,
            (today,),
        ).fetchone()
    return dict(row)


def revenue_by_category(days: int = 7) -> list[dict]:
    since = _since_date(days)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.category,
                   SUM(oi.quantity) AS units,
                   SUM(oi.quantity * oi.unit_price) AS revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN menu m ON oi.menu_id = m.id
            WHERE date(o.created_at) >= ?
              AND o.status != 'cancelled'
            GROUP BY m.category
            ORDER BY revenue DESC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def cogs_by_order(order_id: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(r.qty_per_serving * i.cost_per_unit * oi.quantity), 0) AS cogs
            FROM order_items oi
            JOIN recipe r ON oi.menu_id = r.menu_id
            JOIN inventory i ON i.ingredient = r.ingredient
            WHERE oi.order_id = ?
            """,
            (order_id,),
        ).fetchone()
    return round(float(row["cogs"]), 2)


def cogs_today() -> float:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(r.qty_per_serving * i.cost_per_unit * oi.quantity), 0) AS cogs
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            JOIN recipe r ON oi.menu_id = r.menu_id
            JOIN inventory i ON i.ingredient = r.ingredient
            WHERE date(o.created_at) = ?
              AND o.status != 'cancelled'
            """,
            (today,),
        ).fetchone()
    return round(float(row["cogs"]), 2)


def purchase_spending(days: int = 30) -> float:
    since = _since_date(days)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(poi.estimated_cost), 0) AS spending
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            WHERE po.status = 'received'
              AND date(COALESCE(po.received_at, po.created_at)) >= ?
            """,
            (since,),
        ).fetchone()
    return round(float(row["spending"]), 2)


def estimated_profit_today() -> float:
    today = date.today().isoformat()
    summary = today_summary()
    with get_conn() as conn:
        spending_row = conn.execute(
            """
            SELECT COALESCE(SUM(poi.estimated_cost), 0) AS spending
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            WHERE po.status = 'received'
              AND date(COALESCE(po.received_at, po.created_at)) = ?
            """,
            (today,),
        ).fetchone()
    spending_today = float(spending_row["spending"])
    return round(float(summary["revenue"]) - cogs_today() - spending_today, 2)


def profit_by_day(days: int = 30) -> list[dict]:
    since = _since_date(days)
    with get_conn() as conn:
        revenue_rows = conn.execute(
            """
            SELECT date(o.created_at) AS day,
                   COALESCE(SUM(o.total), 0) AS revenue,
                   COALESCE(SUM(r.qty_per_serving * i.cost_per_unit * oi.quantity), 0) AS cogs
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN recipe r ON r.menu_id = oi.menu_id
            LEFT JOIN inventory i ON i.ingredient = r.ingredient
            WHERE date(o.created_at) >= ?
              AND o.status != 'cancelled'
            GROUP BY date(o.created_at)
            """,
            (since,),
        ).fetchall()

        spending_rows = conn.execute(
            """
            SELECT date(COALESCE(received_at, created_at)) AS day,
                   COALESCE(SUM(poi.estimated_cost), 0) AS spending
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            WHERE po.status = 'received'
              AND date(COALESCE(received_at, created_at)) >= ?
            GROUP BY date(COALESCE(received_at, created_at))
            """,
            (since,),
        ).fetchall()

    spending_map = {r["day"]: float(r["spending"] or 0) for r in spending_rows}
    result = []
    for row in revenue_rows:
        day = row["day"]
        revenue = float(row["revenue"] or 0)
        cogs = float(row["cogs"] or 0)
        spending = float(spending_map.get(day, 0))
        profit = revenue - cogs - spending
        result.append(
            {
                "day": day,
                "revenue": round(revenue, 2),
                "cogs": round(cogs, 2),
                "purchase_spending": round(spending, 2),
                "profit": round(profit, 2),
            }
        )

    result.sort(key=lambda r: r["day"])
    return result


def inventory_value() -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity * cost_per_unit), 0) AS value FROM inventory"
        ).fetchone()
    return round(float(row["value"]), 2)


def waste_risk() -> dict:
    statuses = inventory_mod.get_inventory_status()
    at_risk = [s for s in statuses if s["status"] in {"expired", "expires_today", "expires_soon"}]

    total_value = sum(float(i["quantity"] or 0) * float(i["cost_per_unit"] or 0) for i in at_risk)
    expired_count = sum(1 for i in at_risk if i["status"] == "expired")
    soon_count = sum(1 for i in at_risk if i["status"] in {"expires_today", "expires_soon"})

    return {
        "at_risk_count": len(at_risk),
        "expired_count": expired_count,
        "expiring_count": soon_count,
        "estimated_value_at_risk": round(total_value, 2),
    }


def inventory_risk_summary() -> dict:
    statuses = inventory_mod.get_inventory_status()
    counts = {
        "ok": 0,
        "low": 0,
        "critical": 0,
        "out": 0,
        "expired": 0,
        "expires_today": 0,
        "expires_soon": 0,
    }
    for item in statuses:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


def supplier_spending(days: int = 30) -> list[dict]:
    since = _since_date(days)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(s.name, 'Unassigned') AS supplier,
                   COALESCE(SUM(poi.estimated_cost), 0) AS spending
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            LEFT JOIN suppliers s ON s.id = po.supplier_id
            WHERE po.status = 'received'
              AND date(COALESCE(po.received_at, po.created_at)) >= ?
            GROUP BY COALESCE(s.name, 'Unassigned')
            ORDER BY spending DESC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def top_and_bottom_sellers(days: int = 7) -> dict:
    sales = sales_by_item(days=days)
    if not sales:
        return {"top": [], "bottom": []}

    by_units = sorted(sales, key=lambda x: float(x.get("units_sold") or 0), reverse=True)
    return {
        "top": by_units[:3],
        "bottom": list(reversed(by_units[-3:])),
    }


def dashboard_summary() -> dict:
    summary = today_summary()
    risk = inventory_risk_summary()
    from . import orders as orders_mod

    top_item = None
    sales = sales_by_item(days=1)
    if sales:
        top_item = sales[0]["name"]

    return {
        "revenue_today": round(float(summary["revenue"]), 2),
        "order_count_today": int(summary["num_orders"]),
        "avg_ticket_today": round(float(summary["avg_ticket"]), 2),
        "cogs_today": cogs_today(),
        "estimated_profit_today": estimated_profit_today(),
        "active_orders": len(orders_mod.list_active_orders()),
        "low_stock_count": int(risk.get("low", 0)),
        "critical_stock_count": int(risk.get("critical", 0) + risk.get("out", 0) + risk.get("expired", 0)),
        "expiring_soon_count": int(risk.get("expires_today", 0) + risk.get("expires_soon", 0)),
        "purchase_spending": purchase_spending(days=30),
        "top_selling_item": top_item,
        "alerts_count": len(inventory_mod.get_inventory_alerts()),
    }
