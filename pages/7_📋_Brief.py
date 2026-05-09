"""Owner daily report page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics, inventory, kitchen, purchasing
from backend.bootstrap import ensure_app_ready
from backend.ui_components import VIEW_OWNER, enforce_view_mode, recent_agent_events, render_app_shell, render_metric_card, render_section_header


st.set_page_config(page_title="Daily Report — El Camino", page_icon="📋", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Daily Report", "Executive briefing for today and tomorrow")
summary = analytics.dashboard_summary()
risk = analytics.waste_risk()
active_orders = kitchen.get_active_kitchen_orders()
late_orders = sum(1 for order in active_orders if order.get("is_late"))
restock = purchasing.get_restock_suggestions()

cards = st.columns(5)
with cards[0]:
    render_metric_card("Revenue", f"${summary['revenue_today']:.2f}")
with cards[1]:
    render_metric_card("Orders", summary["order_count_today"])
with cards[2]:
    render_metric_card("Estimated Profit", f"${summary['estimated_profit_today']:.2f}", status="critical" if summary["estimated_profit_today"] < 0 else "healthy")
with cards[3]:
    render_metric_card("Late Orders", late_orders, status="critical" if late_orders else "healthy")
with cards[4]:
    render_metric_card("Inventory Risks", risk["at_risk_count"], status="warning" if risk["at_risk_count"] else "healthy")

render_section_header("Today's Performance")
revenue_df = pd.DataFrame(analytics.revenue_by_day(days=7))
if not revenue_df.empty:
    chart = (
        alt.Chart(revenue_df)
        .mark_bar(color="#D91F26")
        .encode(x=alt.X("day:N", title=None), y=alt.Y("revenue:Q", title="Revenue"), tooltip=["day", "revenue", "num_orders"])
        .properties(height=220)
    )
    st.altair_chart(chart, width='stretch')

left, right = st.columns(2, gap="large")
with left:
    render_section_header("What Went Well")
    top = analytics.top_and_bottom_sellers(days=7).get("top", [])
    if top:
        for item in top:
            st.markdown(f"- {item['name']} sold {item['units_sold']} units")
    else:
        st.markdown("- No sales trends yet")

    render_section_header("Problems Detected")
    alerts = inventory.get_inventory_alerts()
    if alerts:
        for alert in alerts[:5]:
            st.markdown(f"- {alert['message']}")
    else:
        st.markdown("- No critical inventory alerts")

with right:
    render_section_header("Autonomous Actions Taken")
    events = recent_agent_events(limit=8)
    if events:
        for event in events:
            st.markdown(f"- **{event['agent_name']}**: {event['title']} ({event['created_at']})")
    else:
        st.markdown("- No autonomous actions logged")

    render_section_header("Tomorrow Prep Plan")
    tomorrow_steps = [
        "Verify opening inventory for top 5 sellers.",
        "Confirm purchase orders for critical shortages.",
        "Pre-stage ingredients for high-demand items.",
    ]
    for step in tomorrow_steps:
        st.markdown(f"- {step}")

render_section_header("Tomorrow Restock Plan")
if restock:
    for suggestion in restock[:6]:
        st.markdown(
            f"- {suggestion['ingredient']}: order {suggestion['estimated_qty']} {suggestion['unit']} (est ${suggestion['estimated_cost']:.2f})"
        )
else:
    st.caption("No restock actions recommended.")
