"""Shared El Camino UI shell and view-mode components."""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

import streamlit as st

from . import analytics, config, inventory, kitchen, orders, purchasing
from .theme import apply_global_theme, command_card, get_theme_tokens, metric_card, section_header, status_badge


VIEW_MODE_KEY = "el_camino_view_mode"
VIEW_OWNER = "owner"
VIEW_CUSTOMER = "customer"


CUSTOMER_PAGE_ORDER = "pages/1_🍽️_Order.py"
CUSTOMER_PAGE_STATUS = "pages/9_🔎_Order_Status.py"
CUSTOMER_PAGE_MACROS = "pages/12_🥗_Customer_Macros.py"
OWNER_PAGE_DASHBOARD = "pages/0_🧭_Command_Dashboard.py"
OWNER_PAGE_KITCHEN = "pages/2_👨‍🍳_Kitchen.py"
OWNER_PAGE_INVENTORY = "pages/3_📦_Inventory.py"
OWNER_PAGE_PURCHASING = "pages/8_🛒_Purchasing.py"
OWNER_PAGE_SALES = "pages/4_📊_Sales.py"
OWNER_PAGE_REVENUE = "pages/5_💰_Revenue.py"
OWNER_PAGE_ASSISTANT = "pages/6_🤖_Assistant.py"
OWNER_PAGE_AUTOPILOT = "pages/10_🧠_Autopilot.py"
OWNER_PAGE_BRIEF = "pages/7_📋_Brief.py"
OWNER_PAGE_SETTINGS = "pages/7_⚙️_Settings.py"


CUSTOMER_NAV = [
    ("Order", "🍽️", CUSTOMER_PAGE_ORDER),
    ("Macros", "🥗", CUSTOMER_PAGE_MACROS),
    ("Order Status", "🔎", CUSTOMER_PAGE_STATUS),
]

ORDER_DASHBOARD_NAV = [
    ("Order", "🍽️", CUSTOMER_PAGE_ORDER),
    ("Macros", "🥗", CUSTOMER_PAGE_MACROS),
    ("Order Status", "🔎", CUSTOMER_PAGE_STATUS),
]

OWNER_NAV = [
    ("Command Dashboard", "🧭", OWNER_PAGE_DASHBOARD),
    ("Kitchen", "👨‍🍳", OWNER_PAGE_KITCHEN),
    ("Inventory", "📦", OWNER_PAGE_INVENTORY),
    ("Purchasing", "🛒", OWNER_PAGE_PURCHASING),
    ("Sales", "📊", OWNER_PAGE_SALES),
    ("Revenue", "💰", OWNER_PAGE_REVENUE),
    ("Assistant", "🤖", OWNER_PAGE_ASSISTANT),
    ("Autopilot", "🧠", OWNER_PAGE_AUTOPILOT),
    ("Daily Report", "📋", OWNER_PAGE_BRIEF),
    ("Settings", "⚙️", OWNER_PAGE_SETTINGS),
]


def apply_el_camino_theme() -> None:
    apply_global_theme()


def get_view_mode(default: str = VIEW_OWNER) -> str:
    mode = st.session_state.get(VIEW_MODE_KEY)
    if mode not in {VIEW_OWNER, VIEW_CUSTOMER}:
        st.session_state[VIEW_MODE_KEY] = default
        return default
    return mode


def set_view_mode(mode: str) -> None:
    if mode in {VIEW_OWNER, VIEW_CUSTOMER}:
        st.session_state[VIEW_MODE_KEY] = mode


def _switch(path: str) -> None:
    if hasattr(st, "switch_page"):
        st.switch_page(path)


def enforce_view_mode(required_mode: str) -> None:
    mode = get_view_mode(default=required_mode)
    if mode == required_mode:
        return

    st.warning(f"This page belongs to the {required_mode.title()} View. Redirecting.")
    if required_mode == VIEW_CUSTOMER:
        set_view_mode(VIEW_CUSTOMER)
        _switch(CUSTOMER_PAGE_ORDER)
    else:
        set_view_mode(VIEW_OWNER)
        _switch(OWNER_PAGE_DASHBOARD)
    st.stop()


def render_app_shell(view_mode: str) -> None:
    apply_el_camino_theme()
    set_view_mode(view_mode)
    render_sidebar(view_mode)


def render_sidebar(view_mode: str) -> None:
    cfg = config.get_business_config()
    open_flag = str(cfg.get("openStatus", "open")).lower() in {"open", "1", "true", "yes", "on"}
    open_label = "OPEN" if open_flag else "CLOSED"

    with st.sidebar:
        st.markdown("## EL CAMINO")
        st.caption("AI Food Truck Command")
        st.divider()

        nav = ORDER_DASHBOARD_NAV if view_mode == VIEW_CUSTOMER else OWNER_NAV
        for label, icon, path in nav:
            if hasattr(st, "page_link"):
                st.page_link(path, label=label, icon=icon)
            else:
                if st.button(f"{icon} {label}", width='stretch', key=f"nav_{label}"):
                    _switch(path)

        st.divider()
        selected = st.radio(
            "Experience",
            ["Customer View", "Owner View"],
            index=0 if view_mode == VIEW_CUSTOMER else 1,
            label_visibility="collapsed",
        )
        selected_mode = VIEW_CUSTOMER if selected == "Customer View" else VIEW_OWNER
        if selected_mode != view_mode:
            set_view_mode(selected_mode)
            _switch(CUSTOMER_PAGE_ORDER if selected_mode == VIEW_CUSTOMER else OWNER_PAGE_DASHBOARD)

        st.markdown(f"**Service**: `{open_label}`")


def render_top_status_bar() -> None:
    cfg = config.get_business_config()
    summary = analytics.dashboard_summary()
    active_orders = kitchen.get_active_kitchen_orders()
    alerts = inventory.get_inventory_alerts()

    late_orders = sum(1 for order in active_orders if order.get("is_late"))
    rush_mode = "ON" if late_orders >= 2 or len(active_orders) >= 6 else "OFF"
    mode = str(cfg.get("autonomyMode", "Assist")).title()
    open_state = "Open" if str(cfg.get("openStatus", "open")).lower() in {"open", "1", "true", "yes", "on"} else "Closed"

    cols = st.columns(6)
    with cols[0]:
        metric_card("Mode", mode)
    with cols[1]:
        metric_card("Service", open_state, status="healthy" if open_state == "Open" else "warning")
    with cols[2]:
        metric_card("Orders Active", len(active_orders), status="warning" if late_orders else "healthy")
    with cols[3]:
        metric_card("Revenue Today", f"${summary['revenue_today']:.2f}")
    with cols[4]:
        metric_card("Alerts", len(alerts), status="critical" if alerts else "healthy")
    with cols[5]:
        metric_card("Rush Mode", rush_mode, status="warning" if rush_mode == "ON" else "healthy")


def render_metric_card(label: str, value: Any, subtext: str | None = None, status: str | None = None) -> None:
    metric_card(label, value, subtext=subtext, status=status)


def render_status_pill(label: str, status: str) -> str:
    return status_badge(label, status)


def render_agent_card(
    agent_name: str,
    status: str,
    last_action: str,
    next_action: str,
    actions_today: int,
    risk_level: str,
) -> None:
    command_card(
        agent_name,
        (
            f"Last action: {last_action}<br/>"
            f"Next action: {next_action}<br/>"
            f"Actions today: {actions_today}<br/>"
            f"Risk: {risk_level}"
        ),
        status=status,
    )


def render_order_card(order: dict) -> None:
    status = str(order.get("status") or "pending")
    sev = "critical" if order.get("is_late") else ("attention" if status == "preparing" else "warning")
    if status in {"ready", "completed"}:
        sev = "healthy"

    items = ", ".join(f"{line['quantity']}x {line['item_name']}" for line in order.get("items", [])[:3])
    command_card(
        order.get("order_number") or f"Order #{order['id']}",
        (
            f"{order.get('customer_name') or 'Guest'}<br/>"
            f"Status: {status}<br/>"
            f"ETA: {order.get('estimated_ready_at') or 'TBD'}<br/>"
            f"Items: {items or '—'}"
        ),
        status=sev,
    )


@contextmanager
def render_chart_card(title: str, caption: str | None = None):
    st.markdown("<div class='ec-panel'>", unsafe_allow_html=True)
    section_header(title, caption)
    try:
        yield
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


def render_empty_state(title: str, detail: str) -> None:
    command_card(title, detail, status="healthy")


def render_section_header(title: str, caption: str | None = None) -> None:
    section_header(title, caption)


def render_primary_button(label: str, key: str | None = None, use_container_width: bool = True) -> bool:
    return st.button(label, key=key, type="primary", width="stretch" if use_container_width else "content")


def render_warning_banner(text: str) -> None:
    tokens = get_theme_tokens()
    st.markdown(
        (
            "<div style='margin:0.4rem 0 0.9rem;border:1px solid "
            f"{tokens['danger_red']};border-radius:12px;padding:0.7rem 0.9rem;"
            "background:linear-gradient(180deg, rgba(217,31,38,.17), rgba(17,17,17,.96));'>"
            f"<strong style='color:{tokens['danger_red']}'>⚠ {text}</strong></div>"
        ),
        unsafe_allow_html=True,
    )


def recent_agent_events(limit: int = 20) -> list[dict]:
    from .db import get_conn

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_events
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def summarize_kitchen_buckets(orders_list: Iterable[dict]) -> dict[str, int]:
    start_now = 0
    start_soon = 0
    ready_soon = 0
    late = 0

    for order in orders_list:
        if order.get("is_late"):
            late += 1
            continue
        status = str(order.get("status") or "")
        if status == "pending":
            start_now += 1
        elif status == "preparing":
            start_soon += 1
        elif status == "ready":
            ready_soon += 1

    return {
        "start_now": start_now,
        "start_soon": start_soon,
        "ready_soon": ready_soon,
        "late": late,
    }


def purchasing_summary() -> dict[str, Any]:
    suggestions = purchasing.get_restock_suggestions()
    pos = purchasing.list_purchase_orders()

    active_pos = [po for po in pos if po["status"] in {"suggested", "approved"}]
    incoming = [po for po in pos if po["status"] == "approved"]
    spend = sum(float(po.get("estimated_total") or 0) for po in active_pos)

    return {
        "suggestions": suggestions,
        "active_pos": active_pos,
        "incoming": incoming,
        "estimated_spend": round(spend, 2),
    }
