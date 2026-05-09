"""Owner purchasing page with autonomous mock PO flow."""
from __future__ import annotations

import _path_setup  # noqa: F401

import pandas as pd
import streamlit as st

from backend import purchasing
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    render_app_shell,
    render_metric_card,
    render_section_header,
    recent_agent_events,
)


st.set_page_config(page_title="Purchasing — El Camino", page_icon="🛒", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Purchasing", "Mock supplier workflow: Suggested → Created → Approved → Ordered → Received")

suggestions = purchasing.get_restock_suggestions()
pos = purchasing.list_purchase_orders()
active_pos = [po for po in pos if po["status"] in {"suggested", "approved"}]
incoming = [po for po in pos if po["status"] == "approved"]
estimated_spend = sum(float(po.get("estimated_total") or 0) for po in active_pos)

metrics = st.columns(4)
with metrics[0]:
    render_metric_card("Suggested Restocks", len(suggestions), status="warning" if suggestions else "healthy")
with metrics[1]:
    render_metric_card("Active Mock POs", len(active_pos), status="attention" if active_pos else "healthy")
with metrics[2]:
    render_metric_card("Incoming Supplies", len(incoming), status="healthy")
with metrics[3]:
    render_metric_card("Estimated Spend", f"${estimated_spend:.2f}")

st.markdown(
    """
    <div class='ec-panel'>
      <strong>Purchase Lifecycle</strong>
      <div style='margin-top:.5rem;color:#B8B8B8;'>
        Suggested → Created → Approved → Ordered → Received
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1.3, 1], gap="large")

with left:
    render_section_header("Purchase Suggestions")
    if not suggestions:
        st.caption("No restock suggestions currently.")
    else:
        for suggestion in suggestions[:8]:
            with st.container(border=True):
                st.markdown(f"### {suggestion['ingredient']}")
                st.caption(f"Urgency: {suggestion['urgency']} · {suggestion['reason']}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Current", f"{suggestion['current']} {suggestion['unit']}")
                with c2:
                    st.metric("Suggested", f"{suggestion['estimated_qty']} {suggestion['unit']}")
                with c3:
                    st.metric("Est Cost", f"${suggestion['estimated_cost']:.2f}")

                if st.button(
                    "Create Mock PO",
                    key=f"create_po_{suggestion['ingredient']}",
                    type="primary",
                    use_container_width=True,
                ):
                    result = purchasing.create_purchase_order_from_suggestion(
                        ingredient=suggestion["ingredient"],
                        quantity=suggestion["estimated_qty"],
                        supplier_id=suggestion.get("supplier_id"),
                    )
                    if result.get("ok"):
                        st.success(f"PO #{result['purchase_order_id']} created")
                        st.rerun()
                    st.error(result.get("error", "failed_to_create_po"))

with right:
    render_section_header("Autopilot Activity")
    feed = [
        event
        for event in recent_agent_events(limit=20)
        if "purchase" in event["title"].lower() or "po" in event["message"].lower()
    ]
    if not feed:
        st.caption("No recent autopilot purchasing actions.")
    else:
        for event in feed[:6]:
            st.markdown(f"- **{event['title']}** · {event['message']} · `{event['created_at']}`")

    render_section_header("Supplier Comparison")
    if suggestions:
        supplier_df = pd.DataFrame(
            [
                {
                    "Ingredient": suggestion["ingredient"],
                    "Preferred": suggestion.get("supplier_name") or "Unassigned",
                    "Estimated Cost": round(float(suggestion["estimated_cost"]), 2),
                    "Speed": "Fast" if suggestion["urgency"] == "critical" else "Normal",
                }
                for suggestion in suggestions[:8]
            ]
        )
        st.dataframe(supplier_df, use_container_width=True, hide_index=True)

render_section_header("Purchase Order Queue")
if not pos:
    st.caption("No purchase orders yet.")
else:
    for po in pos[:10]:
        with st.container(border=True):
            st.markdown(f"**PO #{po['id']}** · {po.get('supplier_name') or 'Unassigned'} · `{po['status']}`")
            st.caption(f"Created {po['created_at']} · Estimated total ${float(po['estimated_total']):.2f}")
            for item in po.get("items", []):
                st.markdown(f"- {item['ingredient']}: {item['quantity']} {item['unit']} · ${item['estimated_cost']:.2f}")
            b1, b2, b3 = st.columns(3)
            with b1:
                if po["status"] == "suggested" and st.button("Approve", key=f"approve_{po['id']}", use_container_width=True):
                    purchasing.approve_purchase_order(po["id"])
                    st.rerun()
            with b2:
                if po["status"] in {"suggested", "approved"} and st.button("Reject", key=f"reject_{po['id']}", use_container_width=True):
                    purchasing.reject_purchase_order(po["id"])
                    st.rerun()
            with b3:
                if po["status"] == "approved" and st.button("Mark Received", key=f"receive_{po['id']}", type="primary", use_container_width=True):
                    purchasing.mark_purchase_order_received(po["id"])
                    st.rerun()
