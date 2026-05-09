"""Analytics queries — sales rankings, revenue rollups."""
from datetime import date, timedelta
from .db import get_conn


def sales_by_item(days: int = 7):
    """Top items by units sold over the last `days` days."""
    since = (date.today() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.name, m.category,
                      SUM(oi.quantity) AS units_sold,
                      SUM(oi.quantity * oi.unit_price) AS revenue
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.id
               JOIN menu m ON oi.menu_id = m.id
               WHERE date(o.created_at) >= ?
               GROUP BY m.id
               ORDER BY units_sold DESC""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def revenue_by_day(days: int = 30):
    since = (date.today() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date(created_at) AS day,
                      COUNT(*) AS num_orders,
                      SUM(total) AS revenue
               FROM orders
               WHERE date(created_at) >= ?
               GROUP BY date(created_at)
               ORDER BY day ASC""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def today_summary():
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS num_orders,
                      COALESCE(SUM(total), 0) AS revenue,
                      COALESCE(AVG(total), 0) AS avg_ticket
               FROM orders
               WHERE date(created_at) = ?""",
            (today,),
        ).fetchone()
    return dict(row)


def revenue_by_category(days: int = 7):
    since = (date.today() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.category,
                      SUM(oi.quantity) AS units,
                      SUM(oi.quantity * oi.unit_price) AS revenue
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.id
               JOIN menu m ON oi.menu_id = m.id
               WHERE date(o.created_at) >= ?
               GROUP BY m.category
               ORDER BY revenue DESC""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]
