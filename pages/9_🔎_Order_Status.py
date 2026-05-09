"""Customer order tracking page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import streamlit as st

from backend import orders
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_CUSTOMER,
    enforce_view_mode,
    render_app_shell,
    render_metric_card,
    render_section_header,
)


st.set_page_config(page_title="Order Status — El Camino", page_icon="🔎", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_CUSTOMER)
enforce_view_mode(VIEW_CUSTOMER)

render_section_header("Track Your Order", "Flight-board style status tracking")

default_lookup = st.session_state.pop("order_lookup_default", "")
lookup_value = st.text_input("Order number", value=default_lookup, placeholder="EC-1001").strip().upper()

if lookup_value:
    order = orders.get_order_by_number(lookup_value)
    if not order and lookup_value.isdigit():
        order = orders.get_order(int(lookup_value))

    if not order:
        st.error("Order not found. Check your order number.")
    else:
        status = str(order.get("status") or "pending")
        status_map = {
            "pending": "Received",
            "preparing": "Preparing",
            "ready": "Ready",
            "completed": "Completed",
            "cancelled": "Cancelled",
        }
        friendly = status_map.get(status, status.title())

        top = st.columns(3)
        with top[0]:
            render_metric_card("Order", order.get("order_number") or f"#{order['id']}", status="healthy")
        with top[1]:
            render_metric_card("Status", friendly, status="critical" if status == "cancelled" else ("healthy" if status in {"ready", "completed"} else "warning"))
        with top[2]:
            render_metric_card("ETA", order.get("estimated_ready_at") or "TBD")

        progress_steps = [
            ("pending", "Received"),
            ("preparing", "Preparing"),
            ("ready", "Ready"),
            ("completed", "Completed"),
        ]
        current_index = 0
        for idx, (step_key, _) in enumerate(progress_steps):
            if status == step_key:
                current_index = idx
                break
            if status == "cancelled":
                current_index = 0

        cols = st.columns(4)
        for idx, (_, label) in enumerate(progress_steps):
            with cols[idx]:
                done = idx <= current_index and status != "cancelled"
                icon = "✅" if done else "⬜"
                st.markdown(f"{icon} **{label}**")

        st.markdown("### Items")
        for item in order.get("items", []):
            notes = f" · notes: {item['notes']}" if item.get("notes") else ""
            st.markdown(f"- {item['quantity']}x {item['item_name']}{notes}")

        if status == "ready":
            st.success("Your order is ready for pickup.")
        elif status == "completed":
            st.success("Order completed. Thanks for visiting El Camino.")
        elif status == "cancelled":
            st.error("This order was cancelled.")
        else:
            st.info("Your food is in progress.")
