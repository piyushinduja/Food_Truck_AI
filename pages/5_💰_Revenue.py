"""Owner revenue and money analytics."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics
from backend.bootstrap import ensure_app_ready
from backend.ui_components import VIEW_OWNER, enforce_view_mode, render_app_shell, render_metric_card, render_section_header


st.set_page_config(page_title="Revenue — El Camino", page_icon="💰", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Revenue / Money", "Revenue, COGS, margin, and supplier spend")

window_days = st.slider("Window (days)", min_value=7, max_value=90, value=30)
summary = analytics.dashboard_summary()
risk = analytics.waste_risk()
revenue_series = pd.DataFrame(analytics.revenue_by_day(days=window_days))
profit_series = pd.DataFrame(analytics.profit_by_day(days=window_days))
supplier_spending = pd.DataFrame(analytics.supplier_spending(days=window_days))

cards = st.columns(6)
with cards[0]:
    render_metric_card("Revenue Today", f"${summary['revenue_today']:.2f}")
with cards[1]:
    render_metric_card("COGS Today", f"${summary['cogs_today']:.2f}")
with cards[2]:
    render_metric_card("Estimated Profit", f"${summary['estimated_profit_today']:.2f}", status="critical" if summary["estimated_profit_today"] < 0 else "healthy")
with cards[3]:
    render_metric_card("Avg Order Value", f"${summary['avg_ticket_today']:.2f}")
with cards[4]:
    render_metric_card("Purchase Spend", f"${summary['purchase_spending']:.2f}")
with cards[5]:
    render_metric_card("Inventory Risk Value", f"${risk['estimated_value_at_risk']:.2f}", status="warning" if risk["at_risk_count"] else "healthy")

row = st.columns(2, gap="large")
with row[0]:
    if not revenue_series.empty:
        chart = (
            alt.Chart(revenue_series)
            .mark_bar(color="#D91F26")
            .encode(
                x=alt.X("day:N", title=None),
                y=alt.Y("revenue:Q", title="Revenue"),
                tooltip=["day", "num_orders", "revenue"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, width='stretch')

with row[1]:
    if not profit_series.empty:
        line = (
            alt.Chart(profit_series)
            .mark_line(point=True, color="#FFFFFF")
            .encode(
                x=alt.X("day:N", title=None),
                y=alt.Y("profit:Q", title="Profit"),
                tooltip=["day", "profit", "revenue", "cogs", "purchase_spending"],
            )
            .properties(height=260)
        )
        st.altair_chart(line, width='stretch')

render_section_header("Supplier Spending")
if supplier_spending.empty:
    st.caption("No supplier spending in this window.")
else:
    chart = (
        alt.Chart(supplier_spending)
        .mark_bar(color="#8A8A8A")
        .encode(
            x=alt.X("spending:Q", title="Spend"),
            y=alt.Y("supplier:N", sort="-x", title=None),
            tooltip=["supplier", "spending"],
        )
        .properties(height=220)
    )
    st.altair_chart(chart, width='stretch')
