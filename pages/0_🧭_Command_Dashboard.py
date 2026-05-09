"""Owner command dashboard at-a-glance."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics, inventory, kitchen, purchasing
from backend.autopilot import get_autonomy_mode
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    recent_agent_events,
    render_app_shell,
    render_metric_card,
    render_order_card,
    render_section_header,
    render_top_status_bar,
)


st.set_page_config(page_title="Command Dashboard — El Camino", page_icon="🧭", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("El Camino Command", "Operational state at a glance")
render_top_status_bar()

summary = analytics.dashboard_summary()
macro_demand = analytics.customer_macro_demand_summary()
active_orders = kitchen.get_active_kitchen_orders()
alerts = inventory.get_inventory_alerts()
suggestions = purchasing.get_restock_suggestions()
po_queue = purchasing.list_purchase_orders()
risk = analytics.inventory_risk_summary()
recent_orders = active_orders[:5]
recent_events = recent_agent_events(limit=5)

left, middle, right = st.columns([1.2, 1.2, 1], gap="large")

with left:
    render_section_header("Live Orders")
    if recent_orders:
        for order in recent_orders:
            render_order_card(order)
    else:
        st.caption("No active orders.")

    render_section_header("Kitchen Timing")
    late = sum(1 for order in active_orders if order.get("is_late"))
    render_metric_card("Queue", len(active_orders), status="warning" if late else "healthy")
    render_metric_card("Late Orders", late, status="critical" if late else "healthy")
    if active_orders:
        next_order = min(
            active_orders,
            key=lambda o: o.get("remaining_minutes") if o.get("remaining_minutes") is not None else 9999,
        )
        render_metric_card(
            "Next Item to Start",
            next_order.get("order_number") or f"Order #{next_order['id']}",
            subtext=f"Status: {next_order.get('status', 'pending')}",
            status="warning" if next_order.get("status") == "pending" else "healthy",
        )

with middle:
    render_section_header("Inventory Health")
    top = st.columns(2)
    with top[0]:
        render_metric_card("Low Stock", summary["low_stock_count"], status="warning" if summary["low_stock_count"] else "healthy")
        render_metric_card("Critical/Out", summary["critical_stock_count"], status="critical" if summary["critical_stock_count"] else "healthy")
    with top[1]:
        render_metric_card("Expiring Soon", summary["expiring_soon_count"], status="warning" if summary["expiring_soon_count"] else "healthy")
        render_metric_card("Alerts", len(alerts), status="critical" if alerts else "healthy")

    inv_df = pd.DataFrame(
        [
            {"bucket": "OK", "count": risk.get("ok", 0)},
            {"bucket": "Low", "count": risk.get("low", 0)},
            {"bucket": "Critical", "count": risk.get("critical", 0) + risk.get("out", 0)},
            {"bucket": "Expiry", "count": risk.get("expires_today", 0) + risk.get("expires_soon", 0) + risk.get("expired", 0)},
        ]
    )
    if not inv_df.empty and inv_df["count"].sum() > 0:
        chart = (
            alt.Chart(inv_df)
            .mark_arc(innerRadius=46)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color(
                    "bucket:N",
                    scale=alt.Scale(range=["#2F8F57", "#B47A1D", "#D91F26", "#8A8A8A"]),
                    legend=None,
                ),
                tooltip=["bucket", "count"],
            )
            .properties(height=180)
        )
        st.altair_chart(chart, use_container_width=True)

    render_section_header("Purchasing / Restock")
    active_po = [po for po in po_queue if po["status"] in {"suggested", "approved"}]
    render_metric_card("Suggested Restocks", len(suggestions), status="warning" if suggestions else "healthy")
    render_metric_card("Active Mock POs", len(active_po), status="attention" if active_po else "healthy")

with right:
    render_section_header("Money Snapshot")
    render_metric_card("Revenue Today", f"${summary['revenue_today']:.2f}")
    render_metric_card("COGS Today", f"${summary['cogs_today']:.2f}")
    render_metric_card(
        "Estimated Profit",
        f"${summary['estimated_profit_today']:.2f}",
        status="critical" if summary["estimated_profit_today"] < 0 else "healthy",
    )
    render_metric_card("Avg Ticket", f"${summary['avg_ticket_today']:.2f}")

    render_section_header("Customer Macro Demand")
    render_metric_card("Tracking Customers", macro_demand["macro_tracking_customers"])
    requested_strategy = macro_demand["most_requested_macro_strategy"]
    render_metric_card("Requested Strategy", requested_strategy.title() if requested_strategy else "--")
    render_metric_card("Macro-Friendly Item", macro_demand["most_macro_friendly_item"] or "--")
    render_metric_card("Recommended Today", macro_demand["macro_orders_suggested_today"])

    render_section_header("Autopilot / Agent Activity")
    mode_label = get_autonomy_mode().title()
    render_metric_card("Mode", mode_label, status="healthy" if "Full" in mode_label else "warning")
    if recent_events:
        for event in recent_events:
            st.markdown(
                f"- **{event['agent_name']}** · {event['title']} · `{event['created_at']}`",
            )
    else:
        st.caption("No autonomous actions logged yet.")

st.divider()
render_section_header("Mini Trends")
trend_left, trend_mid, trend_right = st.columns(3, gap="large")

revenue_by_day = pd.DataFrame(analytics.revenue_by_day(days=7))
profit_by_day = pd.DataFrame(analytics.profit_by_day(days=7))
sales_by_item = pd.DataFrame(analytics.sales_by_item(days=7)[:5])

with trend_left:
    if not revenue_by_day.empty:
        chart = (
            alt.Chart(revenue_by_day)
            .mark_bar(color="#D91F26")
            .encode(x=alt.X("day:N", title=None), y=alt.Y("revenue:Q", title="Revenue"), tooltip=["day", "revenue", "num_orders"])
            .properties(height=180)
        )
        st.altair_chart(chart, use_container_width=True)

with trend_mid:
    if not profit_by_day.empty:
        chart = (
            alt.Chart(profit_by_day)
            .mark_line(point=True, color="#FFFFFF")
            .encode(x=alt.X("day:N", title=None), y=alt.Y("profit:Q", title="Profit"), tooltip=["day", "profit"])
            .properties(height=180)
        )
        st.altair_chart(chart, use_container_width=True)

with trend_right:
    if not sales_by_item.empty:
        chart = (
            alt.Chart(sales_by_item)
            .mark_bar(color="#8A8A8A")
            .encode(x=alt.X("units_sold:Q", title="Units"), y=alt.Y("name:N", sort="-x", title=None), tooltip=["name", "units_sold", "revenue"])
            .properties(height=180)
        )
        st.altair_chart(chart, use_container_width=True)
