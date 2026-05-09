"""El Camino Command main dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from backend import agent_status, analytics, kitchen, inventory, purchasing
from backend import config as config_mod
from backend.bootstrap import ensure_app_ready
from backend.db import get_conn, reset_db
from backend.seed import seed
from backend.theme import apply_global_theme, command_card, metric_card, section_header


st.set_page_config(
    page_title="El Camino Command",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_app_ready()
apply_global_theme()

cfg = config_mod.get_business_config()
summary = analytics.dashboard_summary()
statuses = agent_status.get_all_agent_statuses()
active_orders = kitchen.get_active_kitchen_orders()
alerts = inventory.get_inventory_alerts()
suggestions = purchasing.get_restock_suggestions()

section_header(
    f"{cfg.get('businessName', 'El Camino Command')}",
    cfg.get("tagline", "Run the truck. Watch the numbers. Serve food on time."),
)

# Top status bar
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    metric_card("Status", str(cfg.get("openStatus", "open")).upper(), status="healthy" if str(cfg.get("openStatus", "open")).lower() == "open" else "attention")
with m2:
    metric_card("Today's Revenue", f"${summary['revenue_today']:.2f}")
with m3:
    metric_card("Orders Today", summary["order_count_today"])
with m4:
    metric_card("Active Orders", summary["active_orders"])
with m5:
    metric_card("Alerts", summary["alerts_count"], status="critical" if summary["alerts_count"] else "healthy")
with m6:
    metric_card("Estimated Profit", f"${summary['estimated_profit_today']:.2f}", status="critical" if summary["estimated_profit_today"] < 0 else "healthy")

section_header("Agent Status", "Customer, kitchen, inventory, and money agents")
agent_cols = st.columns(4)
for col, status in zip(agent_cols, statuses):
    with col:
        body = status["summary"]
        if status["alerts"]:
            body += "<br/>" + "<br/>".join(f"• {a}" for a in status["alerts"][:3])
        command_card(status["agent_name"], body, status=status["status"])

left, right = st.columns([1.2, 1])

with left:
    section_header("Live Orders", "Current queue with ETA")
    if not active_orders:
        command_card("No Active Orders", "Kitchen queue is clear.", status="healthy")
    else:
        for order in active_orders[:8]:
            eta = order.get("estimated_ready_at") or "TBD"
            state = "late" if order.get("is_late") else order.get("status", "pending")
            items = ", ".join(f"{it['quantity']}x {it['item_name']}" for it in order.get("items", []))
            body = (
                f"Customer: {order.get('customer_name') or 'Guest'}<br/>"
                f"Elapsed: {order.get('elapsed_minutes', 0):.1f} min<br/>"
                f"ETA: {eta}<br/>"
                f"Items: {items}"
            )
            command_card(order.get("order_number") or f"Order #{order['id']}", body, status=state)

    section_header("Kitchen Timing", "Start offsets to synchronize hot finish")
    if active_orders:
        for order in active_orders[:4]:
            steps = order.get("timeline", [])
            if not steps:
                continue
            lines = []
            for step in steps[:4]:
                lines.append(
                    f"{step['item_name']}: start +{step['start_offset_minutes']:.1f}m, duration {step['duration_minutes']:.1f}m"
                )
            command_card(
                order.get("order_number") or f"Order #{order['id']}",
                "<br/>".join(lines),
                status="warning" if order.get("is_late") else "healthy",
            )

with right:
    section_header("Inventory Alerts", "Low, critical, out, and expiry safety")
    if not alerts:
        command_card("Inventory", "No active inventory alerts.", status="healthy")
    else:
        for alert in alerts[:8]:
            command_card(alert["ingredient"], alert["message"], status=alert["status"])

    section_header("Purchase Suggestions", "Draft POs requiring owner approval")
    if not suggestions:
        command_card("Purchasing", "No restock suggestions right now.", status="healthy")
    else:
        for s in suggestions[:6]:
            body = (
                f"Need {s['estimated_qty']} {s['unit']} | Est ${s['estimated_cost']:.2f}<br/>"
                f"Reason: {s['reason']}"
            )
            command_card(s["ingredient"], body, status="critical" if s["urgency"] == "critical" else "warning")

    section_header("Money Snapshot", "Revenue, COGS, spend, and risk")
    risk = analytics.waste_risk()
    command_card(
        "Financial View",
        (
            f"Revenue today: ${summary['revenue_today']:.2f}<br/>"
            f"COGS today: ${summary['cogs_today']:.2f}<br/>"
            f"Purchase spend (30d): ${summary['purchase_spending']:.2f}<br/>"
            f"Estimated profit today: ${summary['estimated_profit_today']:.2f}<br/>"
            f"Inventory value at waste risk: ${risk['estimated_value_at_risk']:.2f}"
        ),
        status="critical" if summary["estimated_profit_today"] < 0 else "healthy",
    )

section_header("Agent Activity Feed")
with get_conn() as conn:
    events = conn.execute(
        """
        SELECT * FROM agent_events
        ORDER BY datetime(created_at) DESC
        LIMIT 12
        """
    ).fetchall()

if not events:
    st.caption("No recent agent events.")
else:
    for e in events:
        command_card(
            f"{e['agent_name']} · {e['title']}",
            f"{e['message']}<br/>{e['created_at']}",
            status=e["severity"],
        )

with st.sidebar:
    st.markdown("### Command Controls")
    if st.button("Reset Database", use_container_width=True):
        reset_db()
        seed()
        st.success("Database reset and demo data reloaded.")
        st.rerun()

    st.markdown("---")
    st.markdown("### Role Views")
    if hasattr(st, "page_link"):
        st.page_link("pages/1_🍽️_Order.py", label="Customer: Place Order")
        st.page_link("pages/9_🔎_Order_Status.py", label="Customer: Order Status")
        st.page_link("pages/2_👨‍🍳_Kitchen.py", label="Chef: Kitchen Queue")
        st.page_link("pages/3_📦_Inventory.py", label="Chef: Inventory")
        st.page_link("pages/8_🛒_Purchasing.py", label="Owner: Purchasing")
        st.page_link("pages/5_💰_Revenue.py", label="Owner: Analytics + Money")
        st.page_link("pages/6_🤖_Assistant.py", label="Owner: Assistant")
        st.page_link("pages/7_⚙️_Settings.py", label="Owner: Settings")

    st.markdown("---")
    st.caption("El Camino Command")
    st.caption("Run the truck. Watch the numbers. Serve food on time.")
