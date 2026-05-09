"""Human-approved purchasing workflow page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import streamlit as st

from backend import purchasing
from backend.bootstrap import ensure_app_ready
from backend.db import get_conn
from backend.theme import apply_global_theme, command_card, section_header


st.set_page_config(page_title="Purchasing — El Camino", page_icon="🛒", layout="wide")
ensure_app_ready()
apply_global_theme()

section_header("Purchasing", "Draft, approve, and receive purchase orders")

with get_conn() as conn:
    supplier_rows = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()

supplier_options = {int(r["id"]): r["name"] for r in supplier_rows}
suggestions = purchasing.get_restock_suggestions()

section_header("Restock Suggestions")
if not suggestions:
    command_card("Restock Suggestions", "No suggestions right now.", status="healthy")
else:
    for s in suggestions:
        with st.container(border=True):
            st.markdown(f"### {s['ingredient']}")
            st.caption(f"Status: {s['status']} | Urgency: {s['urgency']} | Reason: {s['reason']}")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Current", f"{s['current']} {s['unit']}")
            with c2:
                st.metric("Estimated Qty", f"{s['estimated_qty']} {s['unit']}")
            with c3:
                st.metric("Estimated Cost", f"${s['estimated_cost']:.2f}")

            default_supplier = s.get("supplier_id") if s.get("supplier_id") in supplier_options else None
            supplier_ids = list(supplier_options.keys())
            selected_supplier = st.selectbox(
                "Supplier",
                supplier_ids,
                index=(supplier_ids.index(default_supplier) if default_supplier in supplier_ids else 0),
                format_func=lambda sid: supplier_options.get(sid, f"Supplier {sid}"),
                key=f"supplier_{s['ingredient']}",
            ) if supplier_ids else None

            if st.button("Create Purchase Order", key=f"create_po_{s['ingredient']}", type="primary"):
                res = purchasing.create_purchase_order_from_suggestion(
                    ingredient=s["ingredient"],
                    quantity=s["estimated_qty"],
                    supplier_id=selected_supplier,
                )
                if res.get("ok"):
                    st.success(f"PO #{res['purchase_order_id']} created for {s['ingredient']}.")
                    st.rerun()
                st.error(res.get("error", "failed_to_create_po"))

section_header("Purchase Order Queue")
status_filter = st.selectbox("Filter by status", ["all", "suggested", "approved", "received", "rejected"], index=0)
pos = purchasing.list_purchase_orders(None if status_filter == "all" else status_filter)

if not pos:
    st.caption("No purchase orders yet.")
else:
    for po in pos:
        with st.container(border=True):
            supplier_name = po.get("supplier_name") or "Unassigned"
            title = f"PO #{po['id']} · {supplier_name}"
            body = (
                f"Status: {po['status']}<br/>"
                f"Estimated total: ${po['estimated_total']:.2f}<br/>"
                f"Created: {po['created_at']}"
            )
            command_card(title, body, status=po["status"])
            for item in po.get("items", []):
                st.markdown(
                    f"- {item['ingredient']}: {item['quantity']} {item['unit']} | ${item['estimated_cost']:.2f}"
                )

            action_cols = st.columns(3)
            with action_cols[0]:
                if po["status"] in {"suggested"} and st.button("Approve", key=f"approve_{po['id']}", use_container_width=True):
                    res = purchasing.approve_purchase_order(po["id"])
                    if res.get("ok"):
                        st.success(f"PO #{po['id']} approved.")
                        st.rerun()
                    st.error(res.get("error", "approve_failed"))
            with action_cols[1]:
                if po["status"] in {"suggested", "approved"} and st.button("Reject", key=f"reject_{po['id']}", use_container_width=True):
                    res = purchasing.reject_purchase_order(po["id"])
                    if res.get("ok"):
                        st.success(f"PO #{po['id']} rejected.")
                        st.rerun()
                    st.error(res.get("error", "reject_failed"))
            with action_cols[2]:
                if po["status"] in {"approved"} and st.button("Mark Received", key=f"receive_{po['id']}", type="primary", use_container_width=True):
                    res = purchasing.mark_purchase_order_received(po["id"])
                    if res.get("ok"):
                        st.success(f"PO #{po['id']} received. Inventory updated.")
                        st.rerun()
                    st.error(res.get("error", "receive_failed"))
