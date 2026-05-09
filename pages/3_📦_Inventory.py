"""Inventory command center with expiry and stock-risk tracking."""
from __future__ import annotations

import _path_setup  # noqa: F401

import pandas as pd
import streamlit as st

from backend import analytics, inventory as inv_mod, purchasing
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, command_card, metric_card, section_header


st.set_page_config(page_title="Inventory — El Camino", page_icon="📦", layout="wide")
ensure_app_ready()
apply_global_theme()

section_header("Inventory Command", "Expiry-aware stock control and menu safety")

status_rows = inv_mod.get_inventory_status()
alerts = inv_mod.get_inventory_alerts()
unavailable_items = inv_mod.get_unavailable_menu_items()
suggestions = purchasing.get_restock_suggestions()

low_count = sum(1 for i in status_rows if i["status"] == "low")
critical_count = sum(1 for i in status_rows if i["status"] in {"critical", "out", "expired"})
expiring_count = sum(1 for i in status_rows if i["status"] in {"expires_today", "expires_soon", "expired"})

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Ingredients", len(status_rows))
with c2:
    metric_card("Low Stock", low_count, status="warning" if low_count else "healthy")
with c3:
    metric_card("Critical/Out", critical_count, status="critical" if critical_count else "healthy")
with c4:
    metric_card("Expiring", expiring_count, status="warning" if expiring_count else "healthy")
with c5:
    metric_card("Inventory Value", f"${analytics.inventory_value():,.2f}")

left, right = st.columns([1.2, 1])

with left:
    section_header("Inventory Table", "Edit quantities, thresholds, supplier links, and expiry dates")
    df = pd.DataFrame(status_rows)
    if not df.empty:
        table_cols = [
            "ingredient",
            "quantity",
            "unit",
            "reorder_threshold",
            "critical_threshold",
            "expiration_date",
            "supplier_id",
            "category",
            "cost_per_unit",
            "status",
        ]
        edit_df = df[table_cols].copy()
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            key="inventory_editor",
            num_rows="fixed",
            column_config={
                "status": st.column_config.TextColumn(disabled=True),
                "ingredient": st.column_config.TextColumn(disabled=True),
            },
        )

        if st.button("Save Inventory Changes", type="primary", use_container_width=True):
            for _, row in edited.iterrows():
                inv_mod.update_inventory_item(
                    ingredient=row["ingredient"],
                    quantity=float(row["quantity"]),
                    unit=row["unit"],
                    reorder_threshold=float(row["reorder_threshold"]),
                    critical_threshold=float(row["critical_threshold"]),
                    expiration_date=(row["expiration_date"] or None),
                    supplier_id=(int(row["supplier_id"]) if pd.notna(row["supplier_id"]) else None),
                    category=row["category"],
                    cost_per_unit=float(row["cost_per_unit"]),
                )
            st.success("Inventory updates saved.")
            st.rerun()

    section_header("Manual Inventory Adjustment")
    ingredients = [i["ingredient"] for i in status_rows]
    if ingredients:
        m1, m2, m3 = st.columns([2.2, 1, 1])
        with m1:
            selected = st.selectbox("Ingredient", ingredients)
        with m2:
            qty = st.number_input("Quantity", min_value=0.0, value=10.0, step=1.0)
        with m3:
            if st.button("Mark Received", use_container_width=True):
                res = inv_mod.mark_inventory_received(selected, qty)
                if res["ok"]:
                    st.success(f"Added {qty} to {selected}.")
                    st.rerun()
                st.error(res.get("error", "update_failed"))

with right:
    section_header("Inventory Alerts")
    if not alerts:
        command_card("Inventory", "No active alerts.", status="healthy")
    else:
        for alert in alerts:
            command_card(alert["ingredient"], alert["message"], status=alert["status"])

    section_header("Restock Suggestions")
    if not suggestions:
        command_card("Restock", "No restock suggestions pending.", status="healthy")
    else:
        for s in suggestions:
            command_card(
                s["ingredient"],
                f"Need {s['estimated_qty']} {s['unit']} | Est ${s['estimated_cost']:.2f}<br/>{s['reason']}",
                status="critical" if s["urgency"] == "critical" else "warning",
            )

section_header("Menu Availability Impact")
if not unavailable_items:
    st.caption("All menu items currently available.")
else:
    for item in unavailable_items:
        blockers = ", ".join(b["ingredient"] for b in item["blocking_ingredients"]) or "unknown blockers"
        command_card(item["menu_name"], f"Blocked by: {blockers}", status="critical")

restocks = inv_mod.list_restocks(limit=20)
if restocks:
    section_header("Received Restock History")
    rdf = pd.DataFrame(restocks)
    st.dataframe(
        rdf[["created_at", "ingredient", "quantity", "unit", "cost", "supplier", "status"]],
        use_container_width=True,
        hide_index=True,
    )
