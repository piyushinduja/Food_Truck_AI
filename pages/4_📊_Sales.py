"""Owner sales page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics
from backend.bootstrap import ensure_app_ready
from backend.ui_components import VIEW_OWNER, enforce_view_mode, render_app_shell, render_metric_card, render_section_header


st.set_page_config(page_title="Sales — El Camino", page_icon="📊", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Sales", "Top sellers, low sellers, category mix, and demand patterns")

days = st.slider("Time window (days)", min_value=1, max_value=60, value=7)
sales = analytics.sales_by_item(days=days)
category = analytics.revenue_by_category(days=days)

if not sales:
    st.info("No sales data for this window.")
else:
    df = pd.DataFrame(sales)
    summary = analytics.top_and_bottom_sellers(days=days)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Top Seller", summary["top"][0]["name"] if summary["top"] else "--")
    with m2:
        render_metric_card("Least Seller", summary["bottom"][0]["name"] if summary["bottom"] else "--")
    with m3:
        render_metric_card("Units Sold", int(df["units_sold"].sum()))
    with m4:
        render_metric_card("Revenue", f"${float(df['revenue'].sum()):.2f}")

    top = st.columns(2, gap="large")
    with top[0]:
        bar = (
            alt.Chart(df.head(8))
            .mark_bar(color="#D91F26")
            .encode(
                x=alt.X("units_sold:Q", title="Units"),
                y=alt.Y("name:N", sort="-x", title=None),
                tooltip=["name", "category", "units_sold", alt.Tooltip("revenue", format="$.2f")],
            )
            .properties(height=280)
        )
        st.altair_chart(bar, use_container_width=True)

    with top[1]:
        if category:
            cdf = pd.DataFrame(category)
            donut = (
                alt.Chart(cdf)
                .mark_arc(innerRadius=56)
                .encode(
                    theta=alt.Theta("revenue:Q"),
                    color=alt.Color("category:N", legend=None),
                    tooltip=["category", "units", alt.Tooltip("revenue", format="$.2f")],
                )
                .properties(height=280)
            )
            st.altair_chart(donut, use_container_width=True)

    st.dataframe(df.rename(columns={"name": "item"}), use_container_width=True, hide_index=True)
