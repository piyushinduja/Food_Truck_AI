"""Kitchen command queue with staggered timing guidance."""
from __future__ import annotations

import _path_setup  # noqa: F401
from datetime import datetime
from time import sleep

import streamlit as st

from backend import kitchen as kitchen_mod
from backend import orders as orders_mod
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, command_card, get_theme_tokens, section_header


st.set_page_config(page_title="Kitchen — El Camino", page_icon="👨‍🍳", layout="wide")
ensure_app_ready()
apply_global_theme()
TOKENS = get_theme_tokens()

section_header("Kitchen Command", "Stagger starts so items finish hot together")


def order_time_badge(order: dict) -> tuple[str, str]:
    if order.get("is_late"):
        return "Late", "critical"
    status = order.get("status")
    if status == "pending":
        return "Start Now", "warning"
    if status == "preparing":
        return "Cooking", "attention"
    if status == "ready":
        return "Ready Soon", "healthy"
    return status or "unknown", "warning"


def timeline_chart_html(steps: list[dict]) -> str:
    if not steps:
        return ""
    max_finish = max(float(s["start_offset_minutes"]) + float(s["duration_minutes"]) for s in steps) or 1
    bars = []
    for step in steps:
        start = (float(step["start_offset_minutes"]) / max_finish) * 100
        width = (float(step["duration_minutes"]) / max_finish) * 100
        color = TOKENS["primary_red"] if step.get("urgency") == "high" else TOKENS["warning"]
        bars.append(
            f"""
            <div style='margin:6px 0;'>
              <div style='font-size:12px;color:{TOKENS["text_secondary"]};margin-bottom:2px;'>
                {step['item_name']} · start +{step['start_offset_minutes']}m · {step['duration_minutes']}m
              </div>
              <div style='position:relative;background:{TOKENS["surface"]};border:1px solid {TOKENS["border"]};height:14px;border-radius:7px;'>
                <div style='position:absolute;left:{start}%;width:{width}%;height:100%;background:{color};border-radius:7px;'></div>
              </div>
            </div>
            """
        )
    return "".join(bars)


auto = st.sidebar.toggle("Auto-refresh (10s)", value=True)
active_orders = kitchen_mod.get_active_kitchen_orders()

if not active_orders:
    st.info("No active kitchen orders.")
else:
    for order in active_orders:
        label, severity = order_time_badge(order)
        order_title = order.get("order_number") or f"Order #{order['id']}"

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.2, 1.2, 1.2, 1])
            with c1:
                st.markdown(f"### {order_title}")
                st.caption(f"Customer: {order.get('customer_name') or 'Guest'}")
            with c2:
                st.metric("Elapsed", f"{order.get('elapsed_minutes', 0):.1f} min")
            with c3:
                eta = order.get("estimated_ready_at") or "TBD"
                st.metric("Est Ready", eta)
            with c4:
                command_card("Kitchen State", label, status=severity)

            st.markdown("**Items**")
            for item in order.get("items", []):
                notes = f" | notes: {item['notes']}" if item.get("notes") else ""
                st.markdown(f"- {item['quantity']}x {item['item_name']}{notes}")

            st.markdown("**Timeline Instructions**")
            steps = order.get("timeline", [])
            if steps:
                now = datetime.utcnow()
                for step in steps:
                    target = step.get("target_start_time")
                    start_state = "Start Now"
                    if target:
                        try:
                            target_dt = datetime.fromisoformat(target)
                            delta = (target_dt - now).total_seconds() / 60
                            if delta > 1:
                                start_state = f"Start in {delta:.1f} min"
                            elif delta < -1:
                                start_state = "Cooking / overdue"
                        except ValueError:
                            pass
                    st.markdown(
                        f"- {step['action']} -> {start_state} (finish {step.get('target_finish_time', 'TBD')})"
                    )
                st.markdown(timeline_chart_html(steps), unsafe_allow_html=True)
            else:
                st.caption("No timeline saved yet.")

            btns = st.columns(4)
            status = order.get("status")
            with btns[0]:
                if status == "pending" and st.button("Start Preparing", key=f"start_{order['id']}", use_container_width=True):
                    orders_mod.advance_status(order["id"])
                    st.rerun()
            with btns[1]:
                if status == "preparing" and st.button("Mark Ready", key=f"ready_{order['id']}", use_container_width=True):
                    orders_mod.advance_status(order["id"])
                    st.rerun()
            with btns[2]:
                if status == "ready" and st.button("Mark Completed", key=f"done_{order['id']}", use_container_width=True):
                    orders_mod.advance_status(order["id"])
                    st.rerun()
            with btns[3]:
                if st.button("Cancel", key=f"cancel_{order['id']}", use_container_width=True):
                    orders_mod.cancel_order(order["id"])
                    st.rerun()

st.markdown("---")
section_header("Recently Completed")
completed = orders_mod.list_orders(status="completed", limit=10)
if completed:
    for order in completed:
        items = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in order["items"])
        command_card(
            order.get("order_number") or f"Order #{order['id']}",
            f"{order.get('customer_name') or 'Guest'} | ${order['total']:.2f}<br/>{items}",
            status="healthy",
        )
else:
    st.caption("No completed orders yet.")

if auto and active_orders:
    sleep(10)
    st.rerun()
