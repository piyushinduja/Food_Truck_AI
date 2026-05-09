"""Owner inventory page with visual-first layout."""
from __future__ import annotations

import _path_setup  # noqa: F401

import altair as alt
import pandas as pd
import streamlit as st

from backend import analytics, inventory, purchasing
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    render_app_shell,
    render_metric_card,
    render_section_header,
)


st.set_page_config(page_title="Inventory — El Camino", page_icon="📦", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Inventory", "Visual health, expiry risk, and menu impact")

status_rows = inventory.get_inventory_status()
alerts = inventory.get_inventory_alerts()
unavailable_items = inventory.get_unavailable_menu_items()
suggestions = purchasing.get_restock_suggestions()

low_count = sum(1 for row in status_rows if row["status"] == "low")
critical_count = sum(1 for row in status_rows if row["status"] in {"critical", "out", "expired"})
expiring_count = sum(1 for row in status_rows if row["status"] in {"expires_today", "expires_soon", "expired"})

metrics = st.columns(5)
with metrics[0]:
    render_metric_card("Total Ingredients", len(status_rows))
with metrics[1]:
    render_metric_card("Low Stock", low_count, status="warning" if low_count else "healthy")
with metrics[2]:
    render_metric_card("Critical/Out", critical_count, status="critical" if critical_count else "healthy")
with metrics[3]:
    render_metric_card("Expiring Soon", expiring_count, status="warning" if expiring_count else "healthy")
with metrics[4]:
    render_metric_card("Inventory Value", f"${analytics.inventory_value():,.2f}")

left, right = st.columns([1.4, 1], gap="large")

status_df = pd.DataFrame(status_rows)

with left:
    render_section_header("Inventory Status")
    if not status_df.empty:
        visual_df = pd.DataFrame(
            [
                {"status": "ok", "count": int((status_df["status"] == "ok").sum())},
                {"status": "low", "count": int((status_df["status"] == "low").sum())},
                {"status": "critical/out", "count": int(status_df["status"].isin(["critical", "out", "expired"]).sum())},
                {"status": "expiry risk", "count": int(status_df["status"].isin(["expires_today", "expires_soon", "expired"]).sum())},
            ]
        )
        bar = (
            alt.Chart(visual_df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("status:N", title=None),
                y=alt.Y("count:Q", title="Count"),
                color=alt.Color(
                    "status:N",
                    scale=alt.Scale(range=["#2F8F57", "#B47A1D", "#D91F26", "#8A8A8A"]),
                    legend=None,
                ),
                tooltip=["status", "count"],
            )
            .properties(height=190)
        )
        st.altair_chart(bar, width='stretch')

        table_cols = [
            "ingredient",
            "quantity",
            "unit",
            "reorder_threshold",
            "critical_threshold",
            "expiration_date",
            "status",
        ]
        st.dataframe(status_df[table_cols], width='stretch', hide_index=True)

with right:
    render_section_header("Alerts")
    if not alerts:
        st.caption("No active alerts.")
    else:
        for alert in alerts[:8]:
            st.markdown(f"- **{alert['ingredient']}** · {alert['message']}")

    render_section_header("Purchasing Suggestions")
    if not suggestions:
        st.caption("No restock suggestions.")
    else:
        for suggestion in suggestions[:6]:
            st.markdown(
                f"- **{suggestion['ingredient']}** · {suggestion['estimated_qty']} {suggestion['unit']} · ${suggestion['estimated_cost']:.2f}"
            )

render_section_header("Menu Availability Impact")
if not unavailable_items:
    st.caption("All menu items are available.")
else:
    for item in unavailable_items[:6]:
        blockers = ", ".join(blocker["ingredient"] for blocker in item["blocking_ingredients"]) or "unknown"
        st.markdown(f"- **{item['menu_name']}** blocked by {blockers}")
