"""Customer order status lookup page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import streamlit as st

from backend import orders as orders_mod
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, command_card, section_header


st.set_page_config(page_title="Order Status — El Camino", page_icon="🔎", layout="centered")
ensure_app_ready()
apply_global_theme()

section_header("Order Status", "Track your order by order number")

order_number = st.text_input("Enter order number", placeholder="EC-1001").strip()

if order_number:
    lookup = order_number.upper()
    order = orders_mod.get_order_by_number(lookup)

    if not order and lookup.isdigit():
        order = orders_mod.get_order(int(lookup))

    if not order:
        st.error("Order not found. Check the order number and try again.")
    else:
        status = order.get("status", "pending")
        command_card(
            f"Order {order.get('order_number') or '#' + str(order['id'])}",
            (
                f"Status: {status}<br/>"
                f"Estimated ready: {order.get('estimated_ready_at') or 'TBD'}<br/>"
                f"Created: {order.get('created_at')}"
            ),
            status="healthy" if status in {"ready", "completed"} else ("attention" if status == "preparing" else "warning"),
        )

        st.markdown("### Items")
        for item in order.get("items", []):
            notes = f" | notes: {item['notes']}" if item.get("notes") else ""
            st.markdown(f"- {item['quantity']}x {item['item_name']}{notes}")

        st.markdown("### Progress")
        progress_steps = ["pending", "preparing", "ready", "completed"]
        labels = {
            "pending": "Received",
            "preparing": "Preparing",
            "ready": "Ready",
            "completed": "Completed",
        }
        current_idx = progress_steps.index(status) if status in progress_steps else 0

        cols = st.columns(4)
        for idx, step in enumerate(progress_steps):
            with cols[idx]:
                marker = "✅" if idx <= current_idx else "⬜"
                st.markdown(f"{marker} {labels[step]}")

        if status == "ready":
            st.success("Your order is ready.")
        elif status == "completed":
            st.success("Your order was completed. Thank you.")
