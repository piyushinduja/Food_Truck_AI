"""Deterministic autopilot orchestration and activity feed."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from . import agent_status, analytics, config, inventory, kitchen, orders, purchasing
from .db import get_conn


MODE_MANUAL = "manual"
MODE_ASSIST = "assist"
MODE_FULL = "full autopilot"


def get_autonomy_mode() -> str:
    raw = str(config.get_config("autonomyMode", "assist") or "assist").strip().lower()
    if raw in {MODE_MANUAL, MODE_ASSIST, MODE_FULL}:
        return raw
    if raw == "full":
        return MODE_FULL
    return MODE_ASSIST


def set_autonomy_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {MODE_MANUAL, MODE_ASSIST, MODE_FULL}:
        normalized = MODE_ASSIST
    config.set_config("autonomyMode", normalized)
    log_agent_event(
        agent_name="Ops Manager Agent",
        severity="attention",
        title="Autonomy mode changed",
        message=f"Autonomy mode set to {normalized.title()}.",
        action_label="Mode Update",
    )
    return normalized


def log_agent_event(
    agent_name: str,
    severity: str,
    title: str,
    message: str,
    action_label: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_events (agent_name, severity, title, message, action_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_name, severity, title, message, action_label),
        )


def get_action_feed(limit: int = 30) -> list[dict]:
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


def _agent_status_rows() -> list[dict]:
    status_rows = agent_status.get_all_agent_statuses()

    # Add deterministic snapshots for specialized agents used on the autopilot page.
    queue = kitchen.get_active_kitchen_orders()
    late = sum(1 for order in queue if order.get("is_late"))
    purchasing_items = purchasing.get_restock_suggestions()
    summary = analytics.dashboard_summary()
    macro_summary = analytics.customer_macro_demand_summary()

    status_rows.append(
        {
            "agent_name": "Customer Agent",
            "status": "healthy" if str(config.get_business_config().get("openStatus", "open")).lower() == "open" else "attention",
            "summary": f"{summary['active_orders']} active orders in service pipeline.",
            "alerts": [],
            "recommended_action": "Monitor checkout throughput.",
        }
    )
    status_rows.append(
        {
            "agent_name": "Customer Macro Agent",
            "status": "healthy" if macro_summary["macro_tracking_customers"] else "attention",
            "summary": f"{macro_summary['macro_tracking_customers']} macro-tracking customer(s), {macro_summary['macro_orders_suggested_today']} recommendation(s) today.",
            "alerts": [],
            "recommended_action": "Help customers build orders from remaining macros.",
        }
    )
    status_rows.append(
        {
            "agent_name": "Kitchen Agent",
            "status": "critical" if late else ("attention" if queue else "healthy"),
            "summary": f"{len(queue)} active kitchen orders, {late} late.",
            "alerts": [],
            "recommended_action": "Rebalance prep starts when late backlog rises.",
        }
    )
    status_rows.append(
        {
            "agent_name": "Purchasing Agent",
            "status": "attention" if purchasing_items else "healthy",
            "summary": f"{len(purchasing_items)} restock suggestions queued.",
            "alerts": [],
            "recommended_action": "Draft purchase orders for critical ingredients.",
        }
    )
    status_rows.append(
        {
            "agent_name": "Money Agent",
            "status": "critical" if float(summary["estimated_profit_today"]) < 0 else "healthy",
            "summary": f"Estimated profit today: ${summary['estimated_profit_today']:.2f}",
            "alerts": [],
            "recommended_action": "Watch margin and purchasing spend balance.",
        }
    )
    status_rows.append(
        {
            "agent_name": "Ops Manager Agent",
            "status": "healthy",
            "summary": f"Mode: {get_autonomy_mode().title()}",
            "alerts": [],
            "recommended_action": "Coordinate customer, kitchen, inventory, and money loops.",
        }
    )
    return status_rows


def get_agent_grid_state() -> list[dict]:
    feed = get_action_feed(limit=200)
    now = datetime.utcnow()
    cards: list[dict] = []

    for row in _agent_status_rows():
        agent_name = row["agent_name"]
        actions = [event for event in feed if event["agent_name"] == agent_name]
        last = actions[0] if actions else None
        actions_today = sum(1 for event in actions if str(event.get("created_at", "")).startswith(now.strftime("%Y-%m-%d")))

        cards.append(
            {
                "agent_name": agent_name,
                "status": row.get("status", "healthy"),
                "last_action": last["title"] if last else "No recent autonomous action",
                "next_action": row.get("recommended_action", "Monitor"),
                "actions_today": actions_today,
                "risk_level": row.get("status", "healthy"),
            }
        )
    return cards


def run_autopilot_cycle() -> dict[str, Any]:
    mode = get_autonomy_mode()
    cycle_actions: list[str] = []

    queue = kitchen.get_active_kitchen_orders()
    late_orders = [order for order in queue if order.get("is_late")]
    pending_orders = [order for order in queue if order.get("status") == "pending"]

    if late_orders:
        log_agent_event(
            "Kitchen Agent",
            "critical",
            "Late kitchen queue detected",
            f"{len(late_orders)} order(s) are late.",
            "Prioritize Late Orders",
        )
        cycle_actions.append(f"flagged {len(late_orders)} late order(s)")

    if mode in {MODE_ASSIST, MODE_FULL} and pending_orders:
        selected = pending_orders[0]
        result = orders.advance_status(selected["id"])
        if result.get("ok"):
            log_agent_event(
                "Kitchen Agent",
                "warning",
                "Auto-started preparation",
                f"Advanced {selected.get('order_number') or selected['id']} to preparing.",
                "Start Preparing",
            )
            cycle_actions.append("advanced one pending order to preparing")

    suggestions = purchasing.get_restock_suggestions()
    critical_suggestions = [s for s in suggestions if s["urgency"] == "critical"]
    if mode in {MODE_ASSIST, MODE_FULL} and critical_suggestions:
        suggestion = critical_suggestions[0]
        created = purchasing.create_purchase_order_from_suggestion(
            ingredient=suggestion["ingredient"],
            quantity=suggestion["estimated_qty"],
            supplier_id=suggestion.get("supplier_id"),
        )
        if created.get("ok"):
            cycle_actions.append(f"drafted PO #{created['purchase_order_id']} for {suggestion['ingredient']}")
            if mode == MODE_FULL and not purchasing.requires_human_approval():
                purchasing.approve_purchase_order(created["purchase_order_id"])
                purchasing.mark_purchase_order_received(created["purchase_order_id"])
                log_agent_event(
                    "Purchasing Agent",
                    "healthy",
                    "Autopilot received purchase order",
                    f"PO #{created['purchase_order_id']} auto-approved and received for {suggestion['ingredient']}.",
                    "Inventory Updated",
                )
                cycle_actions.append(f"auto-received PO #{created['purchase_order_id']}")
            else:
                log_agent_event(
                    "Purchasing Agent",
                    "warning",
                    "Autopilot drafted mock purchase order",
                    f"PO #{created['purchase_order_id']} drafted for {suggestion['ingredient']} pending approval.",
                    "Review PO",
                )

    if not cycle_actions:
        cycle_actions.append("no intervention required")

    summary = analytics.dashboard_summary()
    log_agent_event(
        "Ops Manager Agent",
        "healthy",
        "Autopilot cycle completed",
        (
            f"Cycle actions: {', '.join(cycle_actions)}. "
            f"State: active_orders={summary['active_orders']}, alerts={summary['alerts_count']}, "
            f"profit_today=${summary['estimated_profit_today']:.2f}."
        ),
        "Cycle Complete",
    )

    return {
        "ok": True,
        "mode": mode,
        "actions": cycle_actions,
        "active_orders": summary["active_orders"],
        "alerts": summary["alerts_count"],
        "estimated_profit_today": summary["estimated_profit_today"],
    }
