"""Customer order kiosk view."""
from __future__ import annotations

import _path_setup  # noqa: F401
from collections import defaultdict

import streamlit as st

from backend import agents, analytics, config, orders
from backend.autopilot import log_agent_event
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    CUSTOMER_PAGE_STATUS,
    VIEW_CUSTOMER,
    enforce_view_mode,
    render_app_shell,
    render_empty_state,
    render_metric_card,
    render_primary_button,
    render_section_header,
)


st.set_page_config(page_title="Customer Order — El Camino", page_icon="🍽️", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_CUSTOMER)
enforce_view_mode(VIEW_CUSTOMER)

if "cart" not in st.session_state:
    st.session_state.cart = []
if "last_order_confirmation" not in st.session_state:
    st.session_state.last_order_confirmation = None


cfg = config.get_business_config()
menu_rows = orders.get_menu(only_available=False)
menu_by_id = {item["id"]: item for item in menu_rows}
open_now = str(cfg.get("openStatus", "open")).lower() in {"open", "1", "true", "yes", "on"}


def _timing(item: dict) -> tuple[float, float]:
    prep = float(item.get("prep_time_minutes") or 1)
    cook = float(item.get("cook_time_minutes") or 0)
    return prep, cook


def _cart_total() -> float:
    return sum(float(line["price"]) * int(line["quantity"]) for line in st.session_state.cart)


def _cart_wait_minutes() -> float:
    durations: list[float] = []
    for line in st.session_state.cart:
        item = menu_by_id.get(line["menu_id"])
        if not item:
            continue
        prep, cook = _timing(item)
        per = prep + cook
        qty = max(1, int(line["quantity"]))
        durations.append(per + max(0, qty - 1) * (per * 0.6))
    buffer_minutes = float(cfg.get("defaultPrepBufferMinutes", 2) or 2)
    return round((max(durations) if durations else 0) + buffer_minutes, 1)


def _add_item(item: dict) -> None:
    for line in st.session_state.cart:
        if line["menu_id"] == item["id"] and not line.get("notes"):
            line["quantity"] += 1
            return
    st.session_state.cart.append(
        {
            "menu_id": item["id"],
            "name": item["name"],
            "price": float(item["price"]),
            "quantity": 1,
            "notes": None,
        }
    )


def _remove_line(index: int) -> None:
    if 0 <= index < len(st.session_state.cart):
        st.session_state.cart.pop(index)


def _checkout(customer_name: str) -> None:
    if not open_now:
        st.error("Ordering is currently closed.")
        return
    if not st.session_state.cart:
        st.error("Your cart is empty.")
        return

    result = orders.create_order(
        cart=st.session_state.cart,
        customer_name=(customer_name.strip() or "Guest"),
        source="customer_view",
    )
    if not result.get("ok"):
        st.error(f"Could not place order: {result.get('error')}")
        return

    st.session_state.last_order_confirmation = result
    st.session_state.cart = []
    log_agent_event(
        "Customer Agent",
        "healthy",
        "Customer placed order",
        f"Order {result['order_number']} placed from customer view.",
        "Track Order",
    )


sales = analytics.sales_by_item(days=30)
popular_names = [row["name"] for row in sales[:6]]
if not popular_names:
    popular_names = [item["name"] for item in menu_rows[:6]]

by_category: dict[str, list[dict]] = defaultdict(list)
for item in menu_rows:
    by_category[str(item.get("category") or "other").lower()].append(item)

popular_items = [item for item in menu_rows if item["name"] in popular_names][:6]
category_map: dict[str, list[dict]] = {
    "Popular": popular_items,
    "Burritos": by_category.get("burritos", [])[:6],
    "Tacos": by_category.get("tacos", [])[:6],
    "Sides": by_category.get("sides", [])[:6],
    "Drinks": by_category.get("drinks", [])[:6],
}

header_left, header_mid, header_right, header_cta = st.columns([2, 1, 1, 1])
with header_left:
    st.markdown("## EL CAMINO")
    st.caption("Order in under 30 seconds")
with header_mid:
    render_metric_card("Service", "Open" if open_now else "Closed", status="healthy" if open_now else "critical")
with header_right:
    render_metric_card("Estimated Wait", f"{_cart_wait_minutes():.1f} min" if st.session_state.cart else "~8 min")
with header_cta:
    if st.button("Track Order", use_container_width=True):
        if hasattr(st, "switch_page"):
            st.switch_page(CUSTOMER_PAGE_STATUS)

menu_col, cart_col = st.columns([2.1, 1], gap="large")

with menu_col:
    render_section_header("Menu")
    tabs = st.tabs(list(category_map.keys()))
    for tab, (label, items) in zip(tabs, category_map.items()):
        with tab:
            if not items:
                st.caption("No items in this category.")
                continue
            cols = st.columns(3, gap="medium")
            for idx, item in enumerate(items[:6]):
                with cols[idx % 3]:
                    available = bool(item.get("available", 1))
                    prep, cook = _timing(item)
                    availability = "Available" if available else "Unavailable"
                    status = "healthy" if available else "critical"
                    st.markdown(
                        (
                            "<div class='ec-panel' style='min-height:220px;'>"
                            f"<h4 style='margin:0 0 .25rem 0;'>{item['name']}</h4>"
                            f"<div style='color:#B8B8B8;font-size:.93rem;margin-bottom:.25rem;'>{item.get('description') or ''}</div>"
                            f"<div style='font-weight:700;font-size:1.2rem;margin:.2rem 0;'>${float(item['price']):.2f}</div>"
                            f"<div style='color:#B8B8B8;font-size:.86rem;'>Prep {prep:.1f}m · Cook {cook:.1f}m</div>"
                            f"<div style='margin-top:.45rem;'>{'🟢' if available else '🔴'} {availability}</div>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Add",
                        key=f"add_{label}_{item['id']}",
                        type="primary",
                        use_container_width=True,
                        disabled=not available,
                    ):
                        _add_item(item)
                        st.rerun()

with cart_col:
    render_section_header("Cart")
    if not st.session_state.cart:
        render_empty_state("Cart is empty", "Pick items from the menu to begin your order.")
    else:
        for idx, line in enumerate(st.session_state.cart):
            row1, row2, row3 = st.columns([2.2, 0.7, 0.7])
            with row1:
                st.markdown(f"**{line['name']}**")
                st.caption(f"${line['price']:.2f} each")
            with row2:
                qty = st.number_input(
                    "Qty",
                    min_value=1,
                    max_value=9,
                    value=int(line["quantity"]),
                    step=1,
                    key=f"qty_{idx}",
                    label_visibility="collapsed",
                )
                line["quantity"] = int(qty)
            with row3:
                if st.button("Remove", key=f"rm_{idx}", use_container_width=True):
                    _remove_line(idx)
                    st.rerun()

    subtotal = _cart_total()
    tax_rate = float(cfg.get("taxRate", 0.0825) or 0.0825)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    wait = _cart_wait_minutes()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        render_metric_card("Subtotal", f"${subtotal:.2f}")
        render_metric_card("Tax", f"${tax:.2f}")
    with c2:
        render_metric_card("Total", f"${total:.2f}", status="warning" if total else "healthy")
        render_metric_card("Estimated Wait", f"{wait:.1f} min")

    customer_name = st.text_input("Name", placeholder="Guest")
    if render_primary_button("Place Order"):
        _checkout(customer_name)
        st.rerun()

    with st.expander("Voice Order (optional)", expanded=False):
        st.caption("Try: two carne tacos and a horchata.")
        voice_text = st.text_input("Voice command", placeholder="two carne tacos and a horchata")
        if st.button("Apply Voice Command", use_container_width=True):
            if not voice_text.strip():
                st.error("Enter a voice command first.")
            else:
                try:
                    parsed = agents.parse_voice_order(voice_text, st.session_state.cart)
                    st.session_state.cart = agents.apply_actions_to_cart(
                        st.session_state.cart,
                        parsed.get("actions", []),
                    )
                    st.success(parsed.get("reply") or "Updated cart.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Voice processing failed: {exc}")

if st.session_state.last_order_confirmation:
    confirm = st.session_state.last_order_confirmation
    st.divider()
    render_section_header("Order Confirmed")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Order Number", confirm["order_number"], status="healthy")
    with c2:
        render_metric_card("Estimated Ready", confirm.get("estimated_ready_at") or "TBD")
    with c3:
        render_metric_card("Current Status", "Received", status="warning")

    if st.button("Track this order", use_container_width=False):
        st.session_state["order_lookup_default"] = confirm["order_number"]
        if hasattr(st, "switch_page"):
            st.switch_page(CUSTOMER_PAGE_STATUS)
