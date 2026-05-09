"""Kitchen command queue with live timing and cook assignment guidance."""
from __future__ import annotations

import _path_setup  # noqa: F401
from datetime import datetime, timezone
from html import escape
from time import sleep

import streamlit as st

from backend import orders as orders_mod


st.set_page_config(page_title="Kitchen — El Camino", page_icon="👨‍🍳", layout="wide")


def apply_kitchen_theme() -> None:
    st.markdown(
        """
        <style>
            #MainMenu { visibility:hidden; } footer { visibility:hidden; }
            .stApp { background:radial-gradient(circle at 40% 0%, #0D0D0D 0%, #070707 36%); color:#fff; }
            .main > div { padding:1rem 1.4rem; }
            h1, h2, h3, p, span, label, div { font-family:"Inter", "Segoe UI", sans-serif; }
            [data-testid="stSidebar"] { background:linear-gradient(180deg, #0B0B0B, #070707); border-right:1px solid #2A2A2A; }
            .ec-caption { color:#A8A8A8; font-size:1.05rem; margin-bottom:1rem; }
            .ec-toolbar { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:.9rem; margin:1rem 0 1.2rem; }
            .ec-tile, .ec-order, .ec-chef { background:linear-gradient(180deg, #131313, #101010); border:1px solid #2A2A2A; border-radius:18px; box-shadow:0 12px 28px rgba(0,0,0,.28); }
            .ec-tile { padding:1rem; min-height:106px; }
            .ec-label { color:#A8A8A8; font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; }
            .ec-value { font-size:2rem; font-weight:900; line-height:1.1; margin-top:.25rem; }
            .ec-sub { color:#A8A8A8; margin-top:.25rem; }
            .ready { border-color:#2F8F57; } .watch { border-color:#B47A1D; } .now { border-color:#FF343F; } .late { border-color:#FF343F; background:linear-gradient(180deg, rgba(255,52,63,.16), #101010 58%); }
            .ec-chef-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:.8rem; margin:.8rem 0 1.25rem; }
            .ec-chef { padding:.9rem; }
            .ec-chef-head { display:flex; justify-content:space-between; gap:.7rem; align-items:center; margin-bottom:.55rem; }
            .ec-chef-name { font-size:1.05rem; font-weight:850; }
            .ec-chef-load { color:#FFD36B; font-weight:850; white-space:nowrap; }
            .ec-chef-item { border-top:1px solid #2A2A2A; padding-top:.5rem; margin-top:.5rem; }
            .ec-chef-meta, .ec-item-meta { color:#A8A8A8; font-size:.86rem; margin-top:.18rem; }
            .ec-order { padding:1.1rem; margin-bottom:1rem; }
            .ec-order-top { display:grid; grid-template-columns:minmax(220px, 1.3fr) repeat(4, minmax(145px, .8fr)); gap:.8rem; align-items:stretch; }
            .ec-order-id { font-size:2rem; font-weight:900; }
            .ec-customer { color:#A8A8A8; margin-top:.35rem; }
            .ec-mini { border:1px solid #2A2A2A; border-radius:16px; padding:.75rem .85rem; background:#101010; }
            .ec-mini.ready { border-color:#2F8F57; } .ec-mini.watch { border-color:#B47A1D; } .ec-mini.now, .ec-mini.late { border-color:#FF343F; }
            .ec-mini-value { font-size:1.35rem; font-weight:850; margin-top:.2rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .ec-grid { display:grid; grid-template-columns:1fr 1.2fr; gap:1rem; margin-top:1rem; }
            .ec-panel { border-top:1px solid #2A2A2A; padding-top:.8rem; }
            .ec-list { margin:0; padding-left:1.2rem; } .ec-list li { margin:.42rem 0; }
            .start-now { color:#FF6B72; font-weight:850; } .start-watch { color:#FFD36B; font-weight:850; } .start-ready { color:#69E59C; font-weight:850; }
            .ec-track-row { margin:.7rem 0; } .ec-track-meta { display:flex; justify-content:space-between; color:#A8A8A8; font-size:.9rem; margin-bottom:.25rem; }
            .ec-track { position:relative; background:#111; border:1px solid #2A2A2A; height:16px; border-radius:999px; overflow:hidden; } .ec-bar { position:absolute; top:0; height:100%; border-radius:999px; }
            .stButton > button { border-radius:12px; font-weight:750; border:1px solid #2A2A2A; background:#181818; color:#fff; }
            .stButton > button[kind="primary"] { border-color:transparent; background:linear-gradient(90deg, #B8151B, #D71920); color:#fff; }
            @media (max-width:1200px) { .ec-toolbar, .ec-order-top, .ec-grid { grid-template-columns:1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def timing_for_name(name: str) -> tuple[float, float]:
    text = name.lower()
    if "coke" in text:
        return 0.2, 0.0
    if "lemonade" in text:
        return 1.3, 0.0
    if "horchata" in text:
        return 0.7, 0.0
    if "guacamole" in text:
        return 2.2, 0.0
    if "nachos" in text:
        return 1.5, 3.2
    if "burrito" in text:
        return (2.7, 6.3) if "carne" in text else (2.5, 5.2)
    if "taco" in text:
        return (1.3, 3.7) if "carne" in text or "asada" in text else (1.2, 3.0)
    return 1.0, 3.0


def item_duration(item: dict) -> float:
    prep, cook = timing_for_name(str(item.get("item_name") or ""))
    per = prep + cook
    qty = max(int(item.get("quantity") or 1), 1)
    return round(per + max(0, qty - 1) * per * 0.6, 1)


def enrich_orders(orders: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    enriched = []
    for order in orders:
        created = parse_dt(order.get("created_at")) or now
        steps = []
        longest = 0.0
        for item in order.get("items", []):
            duration = item_duration(item)
            longest = max(longest, duration)
            steps.append({
                "item_name": item.get("item_name"),
                "quantity": item.get("quantity"),
                "notes": item.get("notes"),
                "duration_minutes": duration,
                "action": ("Prep" if timing_for_name(str(item.get("item_name") or ""))[1] <= 0 else "Cook") + f" {item.get('quantity')}x {item.get('item_name')}",
            })
        for step in steps:
            step["start_offset_minutes"] = max(0.0, round(longest - float(step["duration_minutes"]), 1))
            step["target_start_time"] = created.timestamp() + step["start_offset_minutes"] * 60
            step["target_finish_time"] = created.timestamp() + (step["start_offset_minutes"] + float(step["duration_minutes"])) * 60
            step["urgency"] = "high" if step["start_offset_minutes"] == 0 else "normal"
        ready_at = created.timestamp() + (longest + 2) * 60
        elapsed = max(0.0, round((now - created).total_seconds() / 60, 1))
        remaining = round((ready_at - now.timestamp()) / 60, 1)
        d = dict(order)
        d["timeline"] = sorted(steps, key=lambda s: s["start_offset_minutes"])
        d["elapsed_minutes"] = elapsed
        d["remaining_minutes"] = remaining
        d["estimated_ready_ts"] = ready_at
        d["is_late"] = remaining < 0 and order.get("status") != "ready"
        enriched.append(d)
    return enriched


def mmss(minutes: float | None) -> str:
    if minutes is None:
        return "--"
    seconds = max(0, int(round(abs(minutes) * 60)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def urgency(minutes: float | None, late: bool = False) -> tuple[str, str, str]:
    if late or (minutes is not None and minutes < 0):
        return "late", "🚨", "Late"
    if minutes is None:
        return "watch", "⏱️", "Watching"
    if minutes <= 2:
        return "now", "🔥", "Start now"
    if minutes <= 6:
        return "watch", "⏳", "Soon"
    return "ready", "🟢", "On track"


def distribute_work(orders: list[dict], chef_count: int) -> list[dict]:
    chefs = [{"name": f"Chef {idx + 1}", "items": [], "workload": 0.0} for idx in range(max(1, min(3, chef_count)))]
    steps = []
    for order in orders:
        label = f"Order #{order['id']}"
        for step in order.get("timeline", []):
            s = dict(step)
            s["order_label"] = label
            steps.append(s)
    steps.sort(key=lambda s: (float(s.get("start_offset_minutes") or 0), -float(s.get("duration_minutes") or 0)))
    for step in steps:
        chef = min(chefs, key=lambda c: (c["workload"], len(c["items"])))
        chef["items"].append(step)
        chef["workload"] = round(float(chef["workload"]) + float(step.get("duration_minutes") or 0), 1)
    return chefs


def toolbar_html(active: list[dict]) -> str:
    now = datetime.now()
    late_count = sum(1 for o in active if o.get("is_late"))
    remaining = [o.get("remaining_minutes") for o in active if o.get("remaining_minutes") is not None]
    next_minutes = min(remaining) if remaining else None
    klass, icon, label = urgency(next_minutes, late_count > 0)
    active_items = sum(len(o.get("items", [])) for o in active)
    return f"""
    <div class='ec-toolbar'>
      <div class='ec-tile ready'><div class='ec-label'>🕒 Kitchen Clock</div><div class='ec-value'>{now.strftime('%I:%M:%S %p').lstrip('0')}</div><div class='ec-sub'>Local time</div></div>
      <div class='ec-tile {klass}'><div class='ec-label'>⏲️ Next Timer</div><div class='ec-value'>{icon} {mmss(next_minutes)}</div><div class='ec-sub'>{label} · next order countdown</div></div>
      <div class='ec-tile {'late' if late_count else 'ready'}'><div class='ec-label'>⏱️ Line Stopwatch</div><div class='ec-value'>{len(active)} orders · {active_items} items</div><div class='ec-sub'>{late_count} late · queue health</div></div>
    </div>
    """


def render_chefs(active: list[dict], chef_count: int) -> None:
    cards = []
    for chef in distribute_work(active, chef_count):
        body = ""
        for item in chef["items"][:6]:
            body += f"<div class='ec-chef-item'><div><strong>{escape(str(item['action']))}</strong></div><div class='ec-chef-meta'>{escape(str(item['order_label']))} · start +{float(item['start_offset_minutes']):.1f}m · {float(item['duration_minutes']):.1f}m</div></div>"
        if not body:
            body = "<div class='ec-chef-meta'>No assigned items yet.</div>"
        cards.append(f"<div class='ec-chef'><div class='ec-chef-head'><div class='ec-chef-name'>👨‍🍳 {chef['name']}</div><div class='ec-chef-load'>{chef['workload']:.1f}m load</div></div>{body}</div>")
    st.markdown("<div class='ec-chef-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def track_html(steps: list[dict]) -> str:
    if not steps:
        return ""
    max_finish = max(float(s["start_offset_minutes"]) + float(s["duration_minutes"]) for s in steps) or 1
    html = []
    for step in steps:
        left = float(step["start_offset_minutes"]) / max_finish * 100
        width = float(step["duration_minutes"]) / max_finish * 100
        color = "#D71920" if step.get("urgency") == "high" else "#B47A1D"
        html.append(f"<div class='ec-track-row'><div class='ec-track-meta'><span>{escape(str(step['item_name']))}</span><span>start +{float(step['start_offset_minutes']):.1f}m · {float(step['duration_minutes']):.1f}m</span></div><div class='ec-track'><div class='ec-bar' style='left:{left:.2f}%;width:{width:.2f}%;background:{color};'></div></div></div>")
    return "".join(html)


apply_kitchen_theme()
st.title("Kitchen Command")
st.markdown("<div class='ec-caption'>Live clocks, urgency timers, and balanced line assignments.</div>", unsafe_allow_html=True)

auto = st.sidebar.toggle("Auto-refresh (5s)", value=True)
chef_count = st.sidebar.radio("Cooks working now", [1, 2, 3], index=1, horizontal=True)
active = enrich_orders(orders_mod.list_active_orders())

st.markdown(toolbar_html(active), unsafe_allow_html=True)

if active:
    st.subheader("Cook Assignments")
    render_chefs(active, chef_count)
else:
    st.info("No active kitchen orders. Time for a break ☕")

for order in active:
    rem = order.get("remaining_minutes")
    klass, icon, label = urgency(rem, bool(order.get("is_late")))
    ready_label = datetime.fromtimestamp(order["estimated_ready_ts"]).strftime("%-I:%M:%S %p")
    st.markdown(
        f"""
        <div class='ec-order'>
          <div class='ec-order-top'>
            <div><div class='ec-order-id'>Order #{order['id']}</div><div class='ec-customer'>Customer: {escape(str(order.get('customer_name') or 'Guest'))}</div></div>
            <div class='ec-mini {klass}'><div class='ec-label'>Stopwatch</div><div class='ec-mini-value'>⏱️ {float(order['elapsed_minutes']):.1f} min</div><div class='ec-sub'>Elapsed</div></div>
            <div class='ec-mini {klass}'><div class='ec-label'>Countdown</div><div class='ec-mini-value'>{icon} {mmss(rem)}</div><div class='ec-sub'>{label}</div></div>
            <div class='ec-mini {klass}'><div class='ec-label'>Ready Clock</div><div class='ec-mini-value'>{ready_label}</div><div class='ec-sub'>Estimated ready</div></div>
            <div class='ec-mini {klass}'><div class='ec-label'>State</div><div class='ec-mini-value'>{escape(str(order.get('status') or 'pending')).title()}</div><div class='ec-sub'>Kitchen state</div></div>
          </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='ec-grid'><div class='ec-panel'><h4>Items</h4><ul class='ec-list'>", unsafe_allow_html=True)
    for item in order.get("items", []):
        notes = f" · notes: {escape(str(item['notes']))}" if item.get("notes") else ""
        st.markdown(f"<li>{item['quantity']}× {escape(str(item['item_name']))}{notes}</li>", unsafe_allow_html=True)
    st.markdown("</ul></div><div class='ec-panel'><h4>Timeline Instructions</h4><ul class='ec-list'>", unsafe_allow_html=True)
    now_ts = datetime.now(timezone.utc).timestamp()
    for step in order.get("timeline", []):
        delta = (float(step["target_start_time"]) - now_ts) / 60
        state_cls = "start-ready"
        state = f"Start in {delta:.1f} min"
        sym = "⏳"
        if delta <= 1:
            state_cls = "start-now"
            state = "Start Now" if delta >= -1 else "Cooking / overdue"
            sym = "🔥" if delta >= -1 else "🚨"
        elif delta <= 6:
            state_cls = "start-watch"
        finish = datetime.fromtimestamp(float(step["target_finish_time"])).strftime("%-I:%M:%S %p")
        st.markdown(f"<li>{escape(str(step['action']))} → <span class='{state_cls}'>{sym} {escape(state)}</span> <span class='ec-item-meta'>(finish {finish})</span></li>", unsafe_allow_html=True)
    st.markdown("</ul></div></div>" + track_html(order.get("timeline", [])), unsafe_allow_html=True)

    cols = st.columns(3)
    status = order.get("status")
    next_label = {"pending": "Start Preparing", "preparing": "Mark Ready", "ready": "Mark Completed"}.get(status)
    with cols[0]:
        if next_label and st.button(next_label, key=f"adv_{order['id']}", width="stretch", type="primary"):
            orders_mod.advance_status(order["id"])
            st.rerun()
    with cols[2]:
        if st.button("Cancel", key=f"cancel_{order['id']}", width="stretch"):
            orders_mod.cancel_order(order["id"])
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.subheader("Recently Completed")
completed = orders_mod.list_orders(status="completed", limit=8)
if completed:
    for order in completed:
        items = ", ".join(f"{it['quantity']}× {it['item_name']}" for it in order["items"])
        st.markdown(f"**#{order['id']}** · {order['customer_name']} · ${order['total']:.2f} · _{items}_")
else:
    st.caption("No completed orders yet.")

if auto and active:
    sleep(5)
    st.rerun()
