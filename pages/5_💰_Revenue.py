"""Analytics + Money dashboard."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics
from backend.bootstrap import ensure_app_ready
from backend.theme import (
    apply_global_theme,
    command_card,
    get_theme_tokens,
    metric_card,
    section_header,
)


st.set_page_config(page_title="Analytics + Money — El Camino", page_icon="💰", layout="wide")
ensure_app_ready()
apply_global_theme()
TOKENS = get_theme_tokens()

section_header("Analytics + Money", "Revenue, COGS, purchasing spend, and estimated profit")

days = st.sidebar.slider("Window (days)", 7, 90, 30)
summary = analytics.dashboard_summary()
risk = analytics.waste_risk()
profit_series = analytics.profit_by_day(days=days)
revenue_series = analytics.revenue_by_day(days=days)
supplier_spend = analytics.supplier_spending(days=days)

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    metric_card("Revenue Today", f"${summary['revenue_today']:.2f}")
with c2:
    metric_card("Orders Today", summary["order_count_today"])
with c3:
    metric_card("Avg Ticket", f"${summary['avg_ticket_today']:.2f}")
with c4:
    metric_card("COGS Today", f"${summary['cogs_today']:.2f}")
with c5:
    metric_card("Purchase Spend", f"${summary['purchase_spending']:.2f}")
with c6:
    metric_card(
        "Estimated Profit",
        f"${summary['estimated_profit_today']:.2f}",
        status="critical" if summary["estimated_profit_today"] < 0 else "healthy",
    )

info_cols = st.columns(3)
with info_cols[0]:
    command_card("Inventory Risk", f"Expiring/expired items: {risk['at_risk_count']}\nValue at risk: ${risk['estimated_value_at_risk']:.2f}", status="warning" if risk["at_risk_count"] else "healthy")
with info_cols[1]:
    sellers = analytics.top_and_bottom_sellers(days=7)
    top = sellers["top"][0]["name"] if sellers["top"] else "--"
    bottom = sellers["bottom"][0]["name"] if sellers["bottom"] else "--"
    command_card("Sell-through", f"Best: {top}<br/>Least: {bottom}")
with info_cols[2]:
    command_card("Top Selling Item Today", summary.get("top_selling_item") or "No sales yet")

if revenue_series:
    section_header("Revenue Over Time")
    rdf = pd.DataFrame(revenue_series)
    rdf["day"] = pd.to_datetime(rdf["day"])
    rev_chart = (
        alt.Chart(rdf)
        .mark_bar(color=TOKENS["primary_red"])
        .encode(
            x=alt.X("day:T", title="Day"),
            y=alt.Y("revenue:Q", title="Revenue ($)"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("num_orders:Q", title="Orders"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$.2f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(rev_chart, use_container_width=True)

if profit_series:
    section_header("Profit Over Time")
    pdf = pd.DataFrame(profit_series)
    pdf["day"] = pd.to_datetime(pdf["day"])

    line = (
        alt.Chart(pdf)
        .mark_line(point=True, color=TOKENS["text_primary"])
        .encode(
            x="day:T",
            y=alt.Y("profit:Q", title="Profit ($)"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("revenue:Q", format="$.2f"),
                alt.Tooltip("cogs:Q", format="$.2f"),
                alt.Tooltip("purchase_spending:Q", format="$.2f"),
                alt.Tooltip("profit:Q", format="$.2f"),
            ],
        )
        .properties(height=280)
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=TOKENS["text_secondary"]).encode(y="y:Q")
    st.altair_chart((zero + line), use_container_width=True)

section_header("Supplier Spending")
if supplier_spend:
    sdf = pd.DataFrame(supplier_spend)
    sc = (
        alt.Chart(sdf)
        .mark_bar(color=TOKENS["text_secondary"])
        .encode(
            x=alt.X("spending:Q", title="Spend ($)"),
            y=alt.Y("supplier:N", sort="-x", title=None),
            tooltip=["supplier", alt.Tooltip("spending:Q", format="$.2f")],
        )
        .properties(height=220)
    )
    st.altair_chart(sc, use_container_width=True)
else:
    st.caption("No received purchase spending in this period.")
