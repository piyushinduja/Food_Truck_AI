"""Kitchen operations page optimized for at-a-glance workflow."""
from __future__ import annotations

import _path_setup  # noqa: F401
from datetime import datetime
from time import sleep

import streamlit as st

from backend import kitchen, orders
from backend.autopilot import log_agent_event
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    render_app_shell,
    render_metric_card,
    render_section_header,
    summarize_kitchen_buckets,
)


st.set_page_config(page_title="Kitchen — El Camino", page_icon="👨‍🍳", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Kitchen", "Large queue cards and timing controls for busy workers")

active_orders = kitchen.get_active_kitchen_orders()
buckets = summarize_kitchen_buckets(active_orders)
auto = st.toggle("Auto-refresh", value=True)

avg_wait = (
    round(
        sum(max(0.0, float(order.get("elapsed_minutes") or 0)) for order in active_orders) / len(active_orders),
        1,
    )
    if active_orders
    else 0.0
)

next_ready = None
if active_orders:
    candidates = [order for order in active_orders if order.get("estimated_ready_at")]
    if candidates:
        next_ready = min(candidates, key=lambda order: order["estimated_ready_at"])["estimated_ready_at"]

metrics = st.columns(4)
with metrics[0]:
    render_metric_card("Active Orders", len(active_orders), status="warning" if active_orders else "healthy")
with metrics[1]:
    render_metric_card("Average Wait", f"{avg_wait:.1f} min")
with metrics[2]:
    render_metric_card("Late Orders", buckets["late"], status="critical" if buckets["late"] else "healthy")
with metrics[3]:
    render_metric_card("Next Ready", next_ready or "TBD")

if not active_orders:
    st.info("No active kitchen orders.")
else:
    main_col, side_col = st.columns([2.5, 1], gap="large")

    with main_col:
        cols = st.columns(2, gap="medium")
        for idx, order in enumerate(active_orders[:6]):
            with cols[idx % 2]:
                status = str(order.get("status") or "pending")
                is_late = bool(order.get("is_late"))
                order_number = order.get("order_number") or f"Order #{order['id']}"
                remaining = order.get("remaining_minutes")
                eta_text = "TBD" if remaining is None else f"{remaining:.1f} min"
                pill = "🔴 Late" if is_late else ("🟡 Preparing" if status == "preparing" else ("🟢 Ready" if status == "ready" else "⚪ Pending"))
                st.markdown(
                    (
                        "<div class='ec-panel' style='min-height:210px;'>"
                        f"<h4 style='margin:0;'>{order_number}</h4>"
                        f"<div style='color:#B8B8B8;'>Customer: {order.get('customer_name') or 'Guest'}</div>"
                        f"<div style='margin:.4rem 0;font-weight:700;'>{pill}</div>"
                        f"<div style='color:#B8B8B8;'>ETA: {order.get('estimated_ready_at') or 'TBD'}</div>"
                        f"<div style='color:#B8B8B8;'>Remaining: {eta_text}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

                for item in order.get("items", [])[:4]:
                    st.markdown(f"- {item['quantity']}x {item['item_name']}")

                timeline = order.get("timeline", [])
                if timeline:
                    longest = max(float(step.get("start_offset_minutes") or 0) + float(step.get("duration_minutes") or 0) for step in timeline)
                    progress = 0.0
                    if longest > 0:
                        elapsed = max(0.0, float(order.get("elapsed_minutes") or 0))
                        progress = min(1.0, elapsed / longest)
                    st.progress(progress)

                b1, b2, b3 = st.columns(3)
                with b1:
                    if status == "pending" and st.button("Start", key=f"start_{order['id']}", use_container_width=True):
                        orders.advance_status(order["id"])
                        log_agent_event("Kitchen Agent", "warning", "Kitchen status changed", f"{order_number} moved to preparing.", "Start")
                        st.rerun()
                with b2:
                    if status == "preparing" and st.button("Ready", key=f"ready_{order['id']}", use_container_width=True):
                        orders.advance_status(order["id"])
                        log_agent_event("Kitchen Agent", "healthy", "Kitchen status changed", f"{order_number} moved to ready.", "Ready")
                        st.rerun()
                with b3:
                    if status == "ready" and st.button("Complete", key=f"done_{order['id']}", type="primary", use_container_width=True):
                        orders.advance_status(order["id"])
                        log_agent_event("Kitchen Agent", "healthy", "Kitchen status changed", f"{order_number} completed.", "Complete")
                        st.rerun()

    with side_col:
        render_section_header("Queue Buckets")
        render_metric_card("Start Now", buckets["start_now"], status="warning" if buckets["start_now"] else "healthy")
        render_metric_card("Start Soon", buckets["start_soon"], status="attention" if buckets["start_soon"] else "healthy")
        render_metric_card("Ready Soon", buckets["ready_soon"], status="healthy")
        render_metric_card("Late", buckets["late"], status="critical" if buckets["late"] else "healthy")

        st.markdown("### Next Item")
        upcoming = sorted(
            active_orders,
            key=lambda order: order.get("remaining_minutes") if order.get("remaining_minutes") is not None else 9999,
        )
        if upcoming:
            nxt = upcoming[0]
            st.markdown(f"**{nxt.get('order_number') or '#' + str(nxt['id'])}**")
            st.caption(f"Status: {nxt.get('status')} · ETA: {nxt.get('estimated_ready_at') or 'TBD'}")

if auto:
    sleep(8)
    st.rerun()
