"""Sales performance page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, get_theme_tokens, metric_card, section_header


st.set_page_config(page_title="Sales — El Camino", page_icon="📊", layout="wide")
ensure_app_ready()
apply_global_theme()
TOKENS = get_theme_tokens()

section_header("Sales Analyzer", "Top and bottom performers by units and revenue")

days = st.sidebar.slider("Time window (days)", 1, 60, 7)
sales = analytics.sales_by_item(days=days)

if not sales:
    st.info("No sales yet for this window.")
else:
    df = pd.DataFrame(sales)
    summary = analytics.top_and_bottom_sellers(days=days)

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Top Seller", summary["top"][0]["name"] if summary["top"] else "--")
    with c2:
        metric_card("Least Seller", summary["bottom"][0]["name"] if summary["bottom"] else "--")
    with c3:
        metric_card("Units Sold", int(df["units_sold"].sum()))

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=TOKENS["primary_red"])
        .encode(
            x=alt.X("units_sold:Q", title="Units Sold"),
            y=alt.Y("name:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("name:N", title="Item"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("units_sold:Q", title="Units"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$.2f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(chart, use_container_width=True)

    table = df.copy()
    table["revenue"] = table["revenue"].round(2)
    st.dataframe(table.rename(columns={"name": "item"}), use_container_width=True, hide_index=True)

section_header("Revenue by Category")
cat = analytics.revenue_by_category(days=days)
if cat:
    cdf = pd.DataFrame(cat)
    pie = (
        alt.Chart(cdf)
        .mark_arc(innerRadius=64)
        .encode(
            theta=alt.Theta(field="revenue", type="quantitative"),
            color=alt.Color(
                "category:N",
                scale=alt.Scale(
                    range=[
                        TOKENS["primary_red"],
                        TOKENS["text_secondary"],
                        TOKENS["border"],
                        TOKENS["text_primary"],
                        TOKENS["warning"],
                    ]
                ),
            ),
            tooltip=["category", "units", alt.Tooltip("revenue", format="$.2f")],
        )
        .properties(height=320)
    )
    st.altair_chart(pie, use_container_width=True)
else:
    st.caption("No category data available.")
