"""Autopilot overview and cycle controls."""
from __future__ import annotations

import _path_setup  # noqa: F401
from time import sleep

import streamlit as st

from backend import analytics, kitchen, purchasing
from backend.autopilot import get_action_feed, get_agent_grid_state, get_autonomy_mode, run_autopilot_cycle, set_autonomy_mode
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    render_agent_card,
    render_app_shell,
    render_metric_card,
    render_section_header,
    render_warning_banner,
)


st.set_page_config(page_title="Autopilot — El Camino", page_icon="🧠", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

mode = get_autonomy_mode()
summary = analytics.dashboard_summary()
active_orders = kitchen.get_active_kitchen_orders()
late_orders = sum(1 for order in active_orders if order.get("is_late"))
po_active = [po for po in purchasing.list_purchase_orders() if po["status"] in {"suggested", "approved"}]

render_section_header("Autopilot", "Autonomous operations control and activity feed")
if mode == "full autopilot":
    render_warning_banner("FULL AUTOPILOT ACTIVE · El Camino is operating autonomously.")

hero_left, hero_mid, hero_right = st.columns([1.2, 1, 1])
with hero_left:
    st.markdown("### El Camino Autonomy")
    st.caption("Run deterministic autonomous cycles and review agent actions.")
with hero_mid:
    selected = st.selectbox(
        "Current mode",
        ["manual", "assist", "full autopilot"],
        index=["manual", "assist", "full autopilot"].index(mode),
    )
    if selected != mode:
        set_autonomy_mode(selected)
        st.rerun()
with hero_right:
    if st.button("Run Autopilot Cycle", type="primary", width='stretch'):
        result = run_autopilot_cycle()
        st.success("Cycle complete: " + ", ".join(result["actions"]))
        st.rerun()

auto = st.toggle("Auto-refresh", value=True)

render_section_header("Agent Grid")
agents = get_agent_grid_state()
grid = st.columns(3, gap="large")
for idx, agent in enumerate(agents):
    with grid[idx % 3]:
        render_agent_card(
            agent_name=agent["agent_name"],
            status=agent["status"],
            last_action=agent["last_action"],
            next_action=agent["next_action"],
            actions_today=agent["actions_today"],
            risk_level=agent["risk_level"],
        )

render_section_header("Action Feed")
feed = get_action_feed(limit=12)
if not feed:
    st.caption("No autonomous actions logged yet.")
else:
    for event in feed:
        st.markdown(
            f"- **{event['agent_name']}** · {event['title']} · {event['message']} · `{event['created_at']}`"
        )

render_section_header("Business State")
cols = st.columns(6)
with cols[0]:
    render_metric_card("Active Orders", len(active_orders), status="warning" if late_orders else "healthy")
with cols[1]:
    render_metric_card("Late Orders", late_orders, status="critical" if late_orders else "healthy")
with cols[2]:
    render_metric_card("Inventory Alerts", summary["alerts_count"], status="critical" if summary["alerts_count"] else "healthy")
with cols[3]:
    render_metric_card("Active POs", len(po_active), status="attention" if po_active else "healthy")
with cols[4]:
    render_metric_card("Revenue", f"${summary['revenue_today']:.2f}")
with cols[5]:
    render_metric_card(
        "Profit",
        f"${summary['estimated_profit_today']:.2f}",
        status="critical" if summary["estimated_profit_today"] < 0 else "healthy",
    )

if auto:
    sleep(8)
    st.rerun()
