"""Operational status calculators for dashboard agent cards."""
from __future__ import annotations

from . import analytics, config, inventory, kitchen, purchasing
from . import menu as menu_mod


def get_kiosk_agent_status() -> dict:
    cfg = config.get_business_config()
    open_status = str(cfg.get("openStatus", "open")).lower()
    available_items = menu_mod.list_menu(include_unavailable=False)

    if open_status not in {"open", "true", "1"}:
        return {
            "agent_name": "Customer Kiosk Order Agent",
            "status": "attention",
            "summary": "Kiosk is closed.",
            "alerts": ["Business status is set to closed."],
            "recommended_action": "Open service in Settings when ready to accept orders.",
        }

    if not available_items:
        return {
            "agent_name": "Customer Kiosk Order Agent",
            "status": "critical",
            "summary": "No menu items are currently available.",
            "alerts": ["Inventory/expiry constraints made all menu items unavailable."],
            "recommended_action": "Resolve blocked ingredients or expiry dates in Inventory/Settings.",
        }

    return {
        "agent_name": "Customer Kiosk Order Agent",
        "status": "healthy",
        "summary": f"Kiosk is open with {len(available_items)} available items.",
        "alerts": [],
        "recommended_action": "Continue monitoring order throughput.",
    }


def get_inventory_purchasing_agent_status() -> dict:
    alerts = inventory.get_inventory_alerts()
    suggestions = purchasing.get_restock_suggestions()
    critical = [a for a in alerts if a["severity"] == "critical"]

    if critical:
        return {
            "agent_name": "Inventory + Supplies Purchasing Agent",
            "status": "critical",
            "summary": f"{len(critical)} critical inventory issues detected.",
            "alerts": [a["message"] for a in critical[:5]],
            "recommended_action": "Create and review urgent purchase orders now.",
        }

    if suggestions:
        return {
            "agent_name": "Inventory + Supplies Purchasing Agent",
            "status": "attention",
            "summary": f"{len(suggestions)} restock suggestions waiting for owner review.",
            "alerts": [f"{s['ingredient']}: {s['reason']}" for s in suggestions[:5]],
            "recommended_action": "Approve or reject suggested purchase orders.",
        }

    return {
        "agent_name": "Inventory + Supplies Purchasing Agent",
        "status": "healthy",
        "summary": "Inventory levels and purchasing queue are stable.",
        "alerts": [],
        "recommended_action": "No action required.",
    }


def get_analytics_money_agent_status() -> dict:
    summary = analytics.dashboard_summary()
    revenue = float(summary["revenue_today"])
    profit = float(summary["estimated_profit_today"])
    spending = float(summary["purchase_spending"])

    if profit < 0:
        return {
            "agent_name": "Analytics + Money Agent",
            "status": "critical",
            "summary": f"Estimated profit is negative (${profit:,.2f}).",
            "alerts": [
                f"Revenue today: ${revenue:,.2f}",
                f"Purchase spending (30d): ${spending:,.2f}",
            ],
            "recommended_action": "Cut waste and adjust pricing/mix to restore positive margin.",
        }

    if (revenue > 0 and spending > revenue * 2) or (revenue == 0 and spending > 0):
        return {
            "agent_name": "Analytics + Money Agent",
            "status": "attention",
            "summary": "Purchase spending is elevated relative to current revenue.",
            "alerts": [
                f"Revenue today: ${revenue:,.2f}",
                f"Purchase spending (30d): ${spending:,.2f}",
            ],
            "recommended_action": "Review supplier orders and tighten restock cadence.",
        }

    return {
        "agent_name": "Analytics + Money Agent",
        "status": "healthy",
        "summary": "Profitability indicators are within expected range.",
        "alerts": [],
        "recommended_action": "Monitor trend charts for early drift.",
    }


def get_kitchen_monitoring_agent_status() -> dict:
    active = kitchen.get_active_kitchen_orders()
    late_orders = [o for o in active if o.get("is_late")]

    if late_orders:
        return {
            "agent_name": "Kitchen Order Monitoring Agent",
            "status": "critical",
            "summary": f"{len(late_orders)} order(s) are running late.",
            "alerts": [f"{o.get('order_number') or o['id']} is late" for o in late_orders[:5]],
            "recommended_action": "Prioritize late orders and rebalance prep starts.",
        }

    if active:
        return {
            "agent_name": "Kitchen Order Monitoring Agent",
            "status": "healthy",
            "summary": f"{len(active)} active order(s) are on track.",
            "alerts": [],
            "recommended_action": "Keep timeline execution synced with queue.",
        }

    return {
        "agent_name": "Kitchen Order Monitoring Agent",
        "status": "healthy",
        "summary": "No active orders in the queue.",
        "alerts": [],
        "recommended_action": "Stand by for incoming orders.",
    }


def get_all_agent_statuses() -> list[dict]:
    return [
        get_kiosk_agent_status(),
        get_inventory_purchasing_agent_status(),
        get_analytics_money_agent_status(),
        get_kitchen_monitoring_agent_status(),
    ]
