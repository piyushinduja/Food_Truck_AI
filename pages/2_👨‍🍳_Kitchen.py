"""Kitchen page — active orders queue.

Shows pending/preparing/ready orders with elapsed-time badges, items,
and buttons to advance status. Auto-refreshes every 10s.
"""
import _path_setup  # noqa: F401
import streamlit as st
from datetime import datetime, timezone
from time import sleep

from backend import orders as orders_mod


st.set_page_config(page_title="Kitchen — El Camino", page_icon="👨‍🍳", layout="wide")
st.title("👨‍🍳 Kitchen")
st.caption("Active orders, oldest first.")


def time_since(iso_ts: str) -> str:
    """Return '5m ago' style string for a UTC timestamp."""
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return iso_ts
    now = datetime.now(timezone.utc)
    delta = now - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s ago"
    return f"{secs // 3600}h {(secs % 3600) // 60}m ago"


STATUS_COLOR = {
    "pending":   "#f4a261",
    "preparing": "#e76f51",
    "ready":     "#2a9d8f",
}


# Auto-refresh toggle
auto = st.sidebar.toggle("Auto-refresh (10s)", value=True)

active = orders_mod.list_active_orders()

if not active:
    st.info("No active orders. Time for a break ☕")
else:
    # Group by status
    by_status = {"pending": [], "preparing": [], "ready": []}
    for o in active:
        by_status[o["status"]].append(o)

    cols = st.columns(3)
    for col, status in zip(cols, ["pending", "preparing", "ready"]):
        with col:
            st.markdown(f"### <span style='color:{STATUS_COLOR[status]}'>● {status.upper()}</span>", unsafe_allow_html=True)
            st.caption(f"{len(by_status[status])} order(s)")
            for o in by_status[status]:
                with st.container(border=True):
                    head = st.columns([2, 1])
                    with head[0]:
                        st.markdown(f"**Order #{o['id']}**")
                        st.caption(f"{o['customer_name']} · {time_since(o['created_at'])}")
                    with head[1]:
                        st.markdown(f"**${o['total']:.2f}**")

                    for it in o["items"]:
                        line = f"- {it['quantity']}× {it['item_name']}"
                        if it.get("notes"):
                            line += f"  _({it['notes']})_"
                        st.markdown(line)

                    btn_cols = st.columns([3, 1])
                    next_label = {
                        "pending": "Start Preparing",
                        "preparing": "Mark Ready",
                        "ready": "Mark Completed",
                    }[status]
                    with btn_cols[0]:
                        if st.button(next_label, key=f"adv_{o['id']}", use_container_width=True, type="primary"):
                            orders_mod.advance_status(o["id"])
                            st.rerun()
                    with btn_cols[1]:
                        if st.button("✕", key=f"cancel_{o['id']}", use_container_width=True):
                            orders_mod.cancel_order(o["id"])
                            st.rerun()


# Recent completed orders
st.markdown("---")
st.subheader("Recently Completed")
completed = orders_mod.list_orders(status="completed", limit=8)
if completed:
    for o in completed:
        items_str = ", ".join(f"{it['quantity']}× {it['item_name']}" for it in o["items"])
        st.markdown(f"**#{o['id']}** · {o['customer_name']} · ${o['total']:.2f} · _{items_str}_")
else:
    st.caption("No completed orders yet.")


if auto and active:
    sleep(10)
    st.rerun()
