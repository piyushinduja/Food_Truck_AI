"""Owner command dashboard at-a-glance."""
from __future__ import annotations

from datetime import datetime
from html import escape

import _path_setup  # noqa: F401

import streamlit as st

from backend import analytics, config, inventory, kitchen
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    VIEW_OWNER,
    enforce_view_mode,
    recent_agent_events,
    render_app_shell,
)


st.set_page_config(page_title="Command Dashboard - El Camino", page_icon="🧭", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)


def _money(value: float | int | None) -> str:
    return f"${float(value or 0):,.2f}"


def _percent(value: float | int | None) -> str:
    return f"{float(value or 0):.0f}%"


def _time_label(value: str | None) -> str:
    if not value:
        return "TBD"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value
    return dt.strftime("%H:%M")


def _dashboard_css() -> None:
    st.markdown(
        """
        <style>
            .main > div {
                max-width: 1640px;
            }
            [data-testid="stMainBlockContainer"],
            .block-container {
                padding: 1.5rem 3rem 2.2rem 3.25rem !important;
            }
            .ec-command-shell {
                color: #F5F5F5;
            }
            .ec-command-top {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 1.5rem;
                margin: 0 0 0.95rem;
            }
            .ec-command-title h1 {
                margin: 0;
                padding: 0 !important;
                font-size: clamp(2rem, 3vw, 2.65rem);
                font-weight: 850;
                letter-spacing: 0;
                line-height: 1;
            }
            .ec-command-title p {
                margin: 0.64rem 0 0;
                color: #B9B9BD;
                font-size: 1.02rem;
            }
            .ec-clock {
                display: flex;
                align-items: center;
                gap: 1.35rem;
                color: #D5D5D8;
                font-size: 0.95rem;
                white-space: nowrap;
                padding-top: 0.1rem;
            }
            .ec-clock svg {
                width: 18px;
                height: 18px;
                color: #BFC0C5;
            }
            .ec-clock-time {
                color: #8E8E94;
            }
            .ec-kpi-grid {
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 1.18rem;
                margin-bottom: 1.18rem;
            }
            .ec-card {
                position: relative;
                min-width: 0;
                background:
                    radial-gradient(circle at 88% 28%, rgba(255,255,255,0.035), transparent 28%),
                    linear-gradient(180deg, rgba(22,24,27,0.92), rgba(12,13,15,0.96));
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 8px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.035), 0 16px 36px rgba(0,0,0,0.28);
                overflow: hidden;
            }
            .ec-kpi-card {
                min-height: 132px;
                padding: 1.26rem 1.25rem;
            }
            .ec-kicker {
                color: #B7B8BE;
                font-size: 0.75rem;
                font-weight: 850;
                letter-spacing: 0.09em;
                text-transform: uppercase;
            }
            .ec-kpi-value {
                display: flex;
                align-items: center;
                gap: 0.58rem;
                margin-top: 0.9rem;
                color: #FAFAFA;
                font-size: 1.92rem;
                font-weight: 820;
                line-height: 1;
            }
            .ec-kpi-sub {
                margin-top: 0.58rem;
                color: #C8C8CC;
                font-size: 0.92rem;
            }
            .ec-green { color: #4EC06D; }
            .ec-red { color: #FF343F; }
            .ec-yellow { color: #F4C21F; }
            .ec-muted { color: #98999F; }
            .ec-dot {
                display: inline-block;
                width: 0.58rem;
                height: 0.58rem;
                border-radius: 999px;
                background: currentColor;
                box-shadow: 0 0 10px currentColor;
            }
            .ec-kpi-icon {
                position: absolute;
                right: 1.15rem;
                top: 50%;
                transform: translateY(-50%);
                display: grid;
                place-items: center;
                width: 56px;
                height: 56px;
                border: 1px solid rgba(255,255,255,0.32);
                border-radius: 50%;
                color: rgba(255,255,255,0.46);
                font-size: 1.74rem;
            }
            .ec-kpi-icon.is-red {
                border-color: #FF343F;
                color: #FF343F;
            }
            .ec-panel-grid {
                display: grid;
                grid-template-columns: 1.05fr 0.98fr 1.12fr;
                gap: 1.18rem;
                margin-bottom: 0.55rem;
            }
            .ec-panel-grid-bottom {
                display: grid;
                grid-template-columns: 1.76fr 1.04fr;
                gap: 1.18rem;
            }
            .ec-panel {
                min-height: 298px;
                padding: 1.32rem 1.36rem;
            }
            .ec-panel-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 1.55rem;
            }
            .ec-panel-title {
                font-size: 1.22rem;
                font-weight: 780;
                line-height: 1;
            }
            .ec-link {
                color: #C9C9CE;
                font-size: 0.82rem;
            }
            .ec-order-box {
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 8px;
                padding: 1.02rem 1.12rem;
                background: rgba(18,20,23,0.62);
            }
            .ec-order-row,
            .ec-activity-row,
            .ec-money-stats,
            .ec-inventory-body,
            .ec-kitchen-body {
                display: flex;
                align-items: center;
            }
            .ec-order-row {
                justify-content: space-between;
                gap: 1rem;
            }
            .ec-order-id {
                font-size: 1.18rem;
                font-weight: 820;
            }
            .ec-pill {
                border: 1px solid rgba(78,192,109,0.72);
                border-radius: 999px;
                padding: 0.22rem 0.55rem;
                color: #64D77C;
                font-size: 0.68rem;
                font-weight: 850;
                text-transform: uppercase;
            }
            .ec-order-items {
                margin-top: 1.05rem;
                color: #D9D9DD;
                font-size: 0.96rem;
                line-height: 1.45;
            }
            .ec-rule {
                height: 1px;
                margin: 1.0rem 0 0.72rem;
                background: rgba(255,255,255,0.11);
            }
            .ec-order-meta,
            .ec-panel-footer {
                display: flex;
                align-items: center;
                justify-content: space-between;
                color: #BCBCC2;
                font-size: 0.86rem;
            }
            .ec-panel-footer {
                justify-content: flex-start;
                gap: 0.7rem;
                margin-top: 1.1rem;
            }
            .ec-timeline {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 0;
                margin: 0.38rem 0 1.82rem;
                position: relative;
            }
            .ec-timeline::before {
                content: "";
                position: absolute;
                left: 8%;
                right: 8%;
                top: 8px;
                height: 2px;
                background: rgba(255,255,255,0.38);
            }
            .ec-step {
                position: relative;
                z-index: 1;
                display: grid;
                justify-items: center;
                gap: 0.78rem;
                color: #C7C7CC;
                font-size: 0.84rem;
            }
            .ec-step span:first-child {
                display: block;
                width: 16px;
                height: 16px;
                border: 2px solid #BABCC2;
                background: #777C84;
                border-radius: 50%;
            }
            .ec-step.active {
                color: #FF343F;
                font-weight: 750;
            }
            .ec-step.active span:first-child {
                background: #D91F26;
                border-color: #F5F5F5;
            }
            .ec-kitchen-body {
                align-items: stretch;
                gap: 1.7rem;
            }
            .ec-queue-card {
                width: 148px;
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 8px;
                padding: 1.1rem 1.18rem;
                background: rgba(18,20,23,0.6);
            }
            .ec-queue-number {
                margin: 0.48rem 0 0.5rem;
                color: #FF343F;
                font-size: 2rem;
                font-weight: 850;
                line-height: 1;
            }
            .ec-next-action {
                padding-top: 0.62rem;
                color: #DADAE0;
            }
            .ec-next-action strong {
                display: block;
                margin: 0.42rem 0 0.22rem;
                color: #FFFFFF;
                font-size: 1.02rem;
            }
            .ec-inventory-body {
                display: grid;
                grid-template-columns: minmax(0, 1fr) clamp(118px, 34%, 160px);
                align-items: center;
                gap: 1rem;
            }
            .ec-inventory-list {
                min-width: 0;
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 8px;
                overflow: hidden;
            }
            .ec-inventory-line {
                display: grid;
                grid-template-columns: 16px 1fr auto;
                align-items: center;
                gap: 0.52rem;
                min-height: 42px;
                padding: 0 0.84rem;
                border-bottom: 1px solid rgba(255,255,255,0.11);
                color: #D3D3D8;
                font-size: 0.94rem;
            }
            .ec-inventory-line:last-child {
                border-bottom: 0;
            }
            .ec-dot-small {
                width: 9px;
                height: 9px;
                border-radius: 999px;
                background: currentColor;
            }
            .ec-donut {
                width: clamp(118px, 100%, 160px);
                aspect-ratio: 1;
                border-radius: 50%;
                display: grid;
                place-items: center;
                justify-self: end;
                background: var(--donut);
                box-shadow: inset 0 0 22px rgba(255,255,255,0.06);
            }
            .ec-donut-center {
                display: grid;
                place-items: center;
                width: 60%;
                aspect-ratio: 1;
                border-radius: 50%;
                background: radial-gradient(circle at 48% 32%, #202328, #0D0E10 70%);
                text-align: center;
            }
            .ec-donut-number {
                font-size: clamp(1.55rem, 3.2vw, 2.05rem);
                font-weight: 860;
                line-height: 1;
            }
            .ec-donut-label {
                margin-top: 0.4rem;
                color: #C6C6CB;
                font-size: clamp(0.64rem, 1.3vw, 0.78rem);
            }
            .ec-money-panel {
                min-height: 252px;
                padding-top: 1rem;
                padding-bottom: 1rem;
            }
            .ec-money-panel .ec-panel-header,
            .ec-activity-panel .ec-panel-header {
                margin-bottom: 1.05rem;
            }
            .ec-money-stats {
                align-items: flex-end;
                gap: 1.38rem;
            }
            .ec-money-stat {
                min-width: 135px;
                padding-right: 1.6rem;
                border-right: 1px solid rgba(255,255,255,0.12);
            }
            .ec-money-stat:last-of-type {
                border-right: 0;
            }
            .ec-money-label {
                color: #B9B9BE;
                font-size: 0.88rem;
            }
            .ec-money-value {
                margin-top: 0.62rem;
                font-size: 1.64rem;
                font-weight: 850;
                line-height: 1;
            }
            .ec-chart {
                flex: 1;
                min-width: 240px;
                height: 124px;
            }
            .ec-select {
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 6px;
                padding: 0.52rem 0.72rem;
                color: #DADAE0;
                font-size: 0.82rem;
                min-width: 112px;
                text-align: left;
            }
            .ec-activity-panel {
                min-height: 252px;
                padding-top: 1rem;
                padding-bottom: 1rem;
            }
            .ec-activity-list {
                display: grid;
                gap: 0.48rem;
            }
            .ec-activity-row {
                align-items: flex-start;
                gap: 0.86rem;
            }
            .ec-activity-icon {
                display: grid;
                place-items: center;
                width: 35px;
                height: 35px;
                border-radius: 50%;
                flex: 0 0 auto;
                background: rgba(255,255,255,0.08);
                color: #E3E3E6;
                font-size: 1.12rem;
            }
            .ec-activity-icon.warn {
                background: rgba(180,122,29,0.28);
                color: #F18B18;
            }
            .ec-activity-copy {
                flex: 1;
                min-width: 0;
            }
            .ec-activity-title {
                color: #FAFAFA;
                font-weight: 680;
                font-size: 0.92rem;
                line-height: 1.1;
            }
            .ec-activity-detail {
                margin-top: 0.16rem;
                color: #B9B9BE;
                font-size: 0.82rem;
                line-height: 1.22;
            }
            .ec-activity-time {
                color: #94959C;
                font-size: 0.78rem;
                white-space: nowrap;
            }
            @media (max-width: 1280px) {
                .ec-kpi-grid,
                .ec-panel-grid,
                .ec-panel-grid-bottom {
                    grid-template-columns: 1fr 1fr;
                }
                .ec-kpi-grid .ec-kpi-card:last-child {
                    grid-column: span 2;
                }
            }
            @media (max-width: 760px) {
                .ec-command-top,
                .ec-money-stats,
                .ec-inventory-body,
                .ec-kitchen-body {
                    flex-direction: column;
                    align-items: stretch;
                }
                .ec-kpi-grid,
                .ec-panel-grid,
                .ec-panel-grid-bottom {
                    grid-template-columns: 1fr;
                }
                .ec-kpi-grid .ec-kpi-card:last-child {
                    grid-column: auto;
                }
                .ec-clock {
                    justify-content: flex-start;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value: str, sub: str, icon: str, alert: bool = False, dot: str | None = None) -> str:
    dot_html = f"<span class='ec-dot {dot}'></span>" if dot else ""
    icon_class = "ec-kpi-icon is-red" if alert else "ec-kpi-icon"
    return (
        "<div class='ec-card ec-kpi-card'>"
        f"<div class='ec-kicker'>{escape(label)}</div>"
        f"<div class='ec-kpi-value'>{dot_html}<span>{escape(value)}</span></div>"
        f"<div class='ec-kpi-sub'>{sub}</div>"
        f"<div class='{icon_class}'>{icon}</div>"
        "</div>"
    )


def _safe_order_card(order: dict | None) -> str:
    if not order:
        return (
            "<div class='ec-order-box'>"
            "<div class='ec-order-row'><div class='ec-order-id'>No Live Orders</div><span class='ec-pill'>Clear</span></div>"
            "<div class='ec-order-items'>The kitchen queue is clear.</div>"
            "<div class='ec-rule'></div><div class='ec-order-meta'><span>Ordered --:--</span><span>Guest</span></div>"
            "</div>"
        )

    order_id = escape(order.get("order_number") or f"EC-{int(order.get('id', 0)):04d}")
    status = escape(str(order.get("status") or "pending").replace("_", " ").upper())
    eta = _time_label(order.get("estimated_ready_at"))
    customer = escape(order.get("customer_name") or "Guest")
    ordered = _time_label(order.get("created_at"))
    items = order.get("items", [])[:2]
    item_lines = "<br/>".join(
        escape(f"{line.get('quantity', 1)} x {line.get('item_name', 'Item')}")
        for line in items
    ) or "Items pending"

    return (
        "<div class='ec-order-box'>"
        f"<div class='ec-order-row'><div><span class='ec-order-id'>{order_id}</span> "
        f"<span class='ec-pill'>{status}</span></div><span class='ec-muted'>ETA {escape(eta)}</span></div>"
        f"<div class='ec-order-items'>{item_lines}</div>"
        "<div class='ec-rule'></div>"
        f"<div class='ec-order-meta'><span>◷ Ordered {escape(ordered)}</span><span>{customer}</span></div>"
        "</div>"
    )


def _agent_events_html(events: list[dict]) -> str:
    fallback = [
        ("🛒", "", "Reordered limes", "Placed order with Fresh Farms", "4:45 PM"),
        ("⚠", "warn", "Inventory alert", "Beans running low", "4:12 PM"),
        ("🏷", "", "Price optimization", "Updated 2 menu items", "2:58 PM"),
        ("▣", "", "Sales report generated", "Daily summary ready", "8:15 AM"),
    ]
    rows = []
    source = []
    for event in events[:4]:
        source.append(
            (
                "⚠" if event.get("severity") in {"critical", "warning"} else "▣",
                "warn" if event.get("severity") in {"critical", "warning"} else "",
                event.get("title") or event.get("agent_name") or "Activity",
                event.get("message") or event.get("action_label") or "Autopilot activity logged",
                _time_label(event.get("created_at")),
            )
        )
    if not source:
        source = fallback

    for icon, variant, title, detail, time in source:
        rows.append(
            "<div class='ec-activity-row'>"
            f"<div class='ec-activity-icon {variant}'>{escape(icon)}</div>"
            "<div class='ec-activity-copy'>"
            f"<div class='ec-activity-title'>{escape(str(title))}</div>"
            f"<div class='ec-activity-detail'>{escape(str(detail))}</div>"
            "</div>"
            f"<div class='ec-activity-time'>{escape(str(time))}</div>"
            "</div>"
        )
    return "".join(rows)


def _trend_svg(revenue: float) -> str:
    label = _money(revenue).replace(".00", "")
    return f"""
    <svg class="ec-chart" viewBox="0 0 360 150" preserveAspectRatio="none" role="img" aria-label="Revenue trend">
        <defs>
            <linearGradient id="ecLineFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#D91F26" stop-opacity="0.34"/>
                <stop offset="100%" stop-color="#D91F26" stop-opacity="0"/>
            </linearGradient>
        </defs>
        <g stroke="rgba(255,255,255,0.18)" stroke-width="1">
            <line x1="34" y1="18" x2="34" y2="130"/>
            <line x1="34" y1="130" x2="338" y2="130"/>
        </g>
        <g fill="#B8B8BD" font-size="11">
            <text x="0" y="23">$150</text><text x="7" y="62">$100</text><text x="14" y="101">$50</text><text x="20" y="135">$0</text>
            <text x="36" y="147">12 AM</text><text x="112" y="147">6 AM</text><text x="196" y="147">12 PM</text><text x="276" y="147">6 PM</text><text x="326" y="147">12 AM</text>
        </g>
        <path d="M40 128 L66 123 L72 120 L91 119 L100 107 L118 103 L124 92 L139 88 L151 80 L171 75 L190 69 L212 65 L232 58 L249 61 L269 59 L282 52 L287 32 L305 28 L317 33 L330 29 L339 18 L348 16"
              fill="none" stroke="#FF343F" stroke-width="2.3" stroke-linejoin="round"/>
        <path d="M40 128 L66 123 L72 120 L91 119 L100 107 L118 103 L124 92 L139 88 L151 80 L171 75 L190 69 L212 65 L232 58 L249 61 L269 59 L282 52 L287 32 L305 28 L317 33 L330 29 L339 18 L348 16 L348 130 L40 130 Z"
              fill="url(#ecLineFill)"/>
        <text x="318" y="22" fill="#FF343F" font-size="14" font-weight="800">{escape(label)}</text>
    </svg>
    """


summary = analytics.dashboard_summary()
active_orders = kitchen.get_active_kitchen_orders()
alerts = inventory.get_inventory_alerts()
risk = analytics.inventory_risk_summary()
events = recent_agent_events(limit=4)
business_cfg = config.get_business_config()

service_open = str(business_cfg.get("openStatus", "open")).lower() in {"open", "1", "true", "yes", "on"}
service_label = "Open" if service_open else "Closed"
active_order_count = len(active_orders)
critical_alerts = sum(1 for alert in alerts if alert.get("severity") == "critical")
revenue_today = float(summary.get("revenue_today") or 0)
cogs_today = float(summary.get("cogs_today") or 0)
profit_today = float(summary.get("estimated_profit_today") or 0)
margin = (profit_today / revenue_today * 100) if revenue_today else 0

critical_count = int(summary.get("critical_stock_count") or 0)
low_count = int(summary.get("low_stock_count") or 0)
expiring_count = int(summary.get("expiring_soon_count") or 0)
ok_count = int(risk.get("ok", 0))
total_inventory = max(sum(int(v or 0) for v in risk.values()), 1)
yellow_arc = max(0, min(100, round((expiring_count / total_inventory) * 100)))
gray_mid = max(yellow_arc, 100 - round((ok_count / total_inventory) * 100))
donut_style = (
    f"--donut: conic-gradient(#F4C21F 0 {yellow_arc}%, #62666D {yellow_arc}% {gray_mid}%, "
    f"#9A9DA3 {gray_mid}% 82%, #3F434A 82% 100%);"
)

first_order = active_orders[0] if active_orders else None
next_item = "No item queued"
due_text = "Queue clear"
if first_order and first_order.get("items"):
    next_item = first_order["items"][0].get("item_name") or "Next item"
    remaining = first_order.get("remaining_minutes")
    due_text = f"Due in {max(int(round(remaining)), 0)} min" if remaining is not None else "ETA pending"

now = datetime.now()
date_label = now.strftime("%b %-d, %Y") if hasattr(now, "strftime") else "May 9, 2026"
time_label = now.strftime("%-I:%M %p")

_dashboard_css()

dashboard_html = f"""
<div class="ec-command-shell">
    <div class="ec-command-top">
        <div class="ec-command-title">
            <h1>Command Dashboard</h1>
            <p>Operational state at a glance.</p>
        </div>
        <div class="ec-clock">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/>
            </svg>
            <span>{escape(date_label)}</span>
            <span class="ec-clock-time">{escape(time_label)}</span>
        </div>
    </div>

    <div class="ec-kpi-grid">
        {_metric_card("Service Status", service_label, "Assist Mode", "♨", dot="ec-green" if service_open else "ec-red")}
        {_metric_card("Active Orders", str(active_order_count), "In Progress", "▢")}
        {_metric_card("Revenue Today", _money(revenue_today), "vs Yesterday&nbsp;&nbsp;<span class='ec-green'>+18%</span>", "$")}
        {_metric_card("Alerts", str(len(alerts)), f"<span class='ec-red'>{critical_alerts} Critical</span>", "!", alert=bool(alerts))}
        {_metric_card("Profit Today", _money(profit_today), f"{_percent(margin)} Margin", "↗")}
    </div>

    <div class="ec-panel-grid">
        <div class="ec-card ec-panel">
            <div class="ec-panel-header">
                <div class="ec-panel-title">Live Orders</div>
                <div class="ec-link">View all orders&nbsp;&nbsp;›</div>
            </div>
            {_safe_order_card(first_order)}
            <div class="ec-panel-footer"><span class="ec-dot ec-green"></span><span>{active_order_count} active order{'s' if active_order_count != 1 else ''}</span></div>
        </div>

        <div class="ec-card ec-panel">
            <div class="ec-panel-header">
                <div class="ec-panel-title">Kitchen Timing</div>
            </div>
            <div class="ec-timeline">
                <div class="ec-step active"><span></span><span>Queued</span></div>
                <div class="ec-step"><span></span><span>Preparing</span></div>
                <div class="ec-step"><span></span><span>Plating</span></div>
                <div class="ec-step"><span></span><span>Ready</span></div>
            </div>
            <div class="ec-kitchen-body">
                <div class="ec-queue-card">
                    <div class="ec-kicker">Queue Health</div>
                    <div class="ec-queue-number">{active_order_count}</div>
                    <div class="ec-kpi-sub">Order waiting</div>
                </div>
                <div class="ec-next-action">
                    <div class="ec-kicker">Next Action</div>
                    <strong>{'Start preparing' if active_order_count else 'Stand by'}</strong>
                    <div>{escape(next_item)}</div>
                    <div class="ec-kpi-sub">{escape(due_text)}</div>
                </div>
            </div>
        </div>

        <div class="ec-card ec-panel">
            <div class="ec-panel-header">
                <div class="ec-panel-title">Inventory Health</div>
                <div class="ec-link">View inventory&nbsp;&nbsp;›</div>
            </div>
            <div class="ec-inventory-body">
                <div class="ec-inventory-list">
                    <div class="ec-inventory-line"><span class="ec-dot-small ec-red"></span><span>Critical / Out</span><strong>{critical_count}</strong></div>
                    <div class="ec-inventory-line"><span class="ec-dot-small" style="color:#F18B18"></span><span>Low Stock</span><strong>{low_count}</strong></div>
                    <div class="ec-inventory-line"><span class="ec-dot-small ec-yellow"></span><span>Expiring Soon</span><strong>{expiring_count}</strong></div>
                    <div class="ec-inventory-line"><span class="ec-dot-small ec-muted"></span><span>In Stock</span><strong>{ok_count}</strong></div>
                </div>
                <div class="ec-donut" style="{donut_style}">
                    <div class="ec-donut-center">
                        <div>
                            <div class="ec-donut-number">{sum(int(v or 0) for v in risk.values())}</div>
                            <div class="ec-donut-label">Total Items</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="ec-panel-grid-bottom">
        <div class="ec-card ec-panel ec-money-panel">
            <div class="ec-panel-header">
                <div class="ec-panel-title">Money Snapshot</div>
                <div class="ec-select">Today&nbsp;&nbsp;⌄</div>
            </div>
            <div class="ec-money-stats">
                <div class="ec-money-stat">
                    <div class="ec-money-label">Revenue</div>
                    <div class="ec-money-value">{_money(revenue_today)}</div>
                    <div class="ec-kpi-sub">vs Yesterday&nbsp;&nbsp;<span class="ec-green">+18%</span></div>
                </div>
                <div class="ec-money-stat">
                    <div class="ec-money-label">COGS</div>
                    <div class="ec-money-value">{_money(cogs_today)}</div>
                    <div class="ec-kpi-sub">{_percent((cogs_today / revenue_today * 100) if revenue_today else 0)} of Revenue</div>
                </div>
                <div class="ec-money-stat">
                    <div class="ec-money-label">Estimated Profit</div>
                    <div class="ec-money-value">{_money(profit_today)}</div>
                    <div class="ec-kpi-sub"><span class="ec-green">{_percent(margin)} Margin</span></div>
                </div>
                {_trend_svg(revenue_today)}
            </div>
        </div>

        <div class="ec-card ec-panel ec-activity-panel">
            <div class="ec-panel-header">
                <div class="ec-panel-title">Autopilot Activity</div>
                <div class="ec-link">View all activity&nbsp;&nbsp;›</div>
            </div>
            <div class="ec-activity-list">
                {_agent_events_html(events)}
            </div>
        </div>
    </div>
</div>
"""

st.markdown(" ".join(line.strip() for line in dashboard_html.splitlines()), unsafe_allow_html=True)
