"""Customer order page with El Camino menu cards and badges."""
from __future__ import annotations

import _path_setup  # noqa: F401
from collections import defaultdict
from html import escape

import streamlit as st

from backend import agents, orders as orders_mod


st.set_page_config(page_title="Order — El Camino", page_icon="🍽️", layout="wide")

HEALTHY_ITEM_NAMES = {"Veggie Taco", "Lemonade"}
SPECIALTY_ITEM_NAMES = {"Carne Asada Taco", "Horchata"}
CATEGORY_UI = {
    "burritos": ("Burritos", "🌯", 2),
    "drinks": ("Drinks", "🥤", 3),
    "tacos": ("Tacos", "🌮", 3),
    "sides": ("Sides", "🥑", 3),
}

if "cart" not in st.session_state:
    st.session_state.cart = []
if "voice_log" not in st.session_state:
    st.session_state.voice_log = []


def apply_order_theme() -> None:
    st.markdown(
        """
        <style>
            #MainMenu { visibility:hidden; }
            footer { visibility:hidden; }
            header[data-testid="stHeader"] { background:transparent; height:0; }
            .stApp { background: radial-gradient(circle at 40% 0%, #0D0D0D 0%, #070707 36%); color:#fff; }
            .main > div { padding-top:1rem; padding-left:1rem; padding-right:1rem; }
            h1, h2, h3, p, span, label, div { font-family:"Inter", "Segoe UI", sans-serif; }
            [data-testid="stSidebar"] { background:linear-gradient(180deg, #0B0B0B, #070707); border-right:1px solid #2A2A2A; }
            .ec-title { color:#D71920; letter-spacing:.08em; text-transform:uppercase; font-weight:800; margin-bottom:.25rem; }
            .ec-hero { font-size:clamp(2.3rem, 4vw, 3.7rem); font-weight:900; line-height:1; margin-bottom:.45rem; }
            .ec-sub { color:#A8A8A8; font-size:1.15rem; margin-bottom:1.2rem; }
            .ec-section-row { display:flex; align-items:center; gap:.65rem; margin:1.2rem 0 .8rem; }
            .ec-section-title { font-size:2rem; font-weight:850; position:relative; padding-bottom:.32rem; }
            .ec-section-title::after { content:""; position:absolute; left:0; bottom:-3px; width:42px; height:4px; border-radius:99px; background:#D71920; }
            .ec-section-divider { flex:1; height:1px; background:#2A2A2A; margin-left:.2rem; }
            .ec-menu-card { position:relative; overflow:hidden; min-height:262px; border:1px solid #6E665A; border-radius:18px; background:linear-gradient(180deg, #131313, #101010); padding:1rem; box-shadow:0 10px 26px rgba(0,0,0,.3); }
            .ec-card-head { display:flex; gap:.85rem; min-width:0; align-items:flex-start; }
            .ec-thumb { width:76px; height:76px; border-radius:999px; flex-shrink:0; background:radial-gradient(circle at 30% 30%, #4B4B4B, #1C1C1C 72%); border:1px solid #6E665A; display:flex; align-items:center; justify-content:center; font-size:2rem; }
            .ec-card-body { min-width:0; flex:1; }
            .ec-badges { display:flex; flex-wrap:wrap; gap:.34rem; min-height:1.45rem; margin-bottom:.36rem; }
            .ec-badge { display:inline-flex; width:fit-content; align-items:center; gap:.22rem; border-radius:999px; padding:.2rem .48rem; font-size:.66rem; font-weight:800; text-transform:uppercase; letter-spacing:.03em; background:#101010; border:1px solid rgba(255,255,255,.14); }
            .ec-badge.healthy { color:#69E59C; border-color:#24B56A; }
            .ec-badge.specialty { color:#FFD36B; border-color:#D6A22A; }
            .ec-name { font-size:clamp(1.25rem, 2vw, 1.85rem); font-weight:850; line-height:1.08; overflow-wrap:normal; word-break:normal; hyphens:none; }
            .ec-price { color:#FF343F; font-size:clamp(1.65rem, 2.4vw, 2.2rem); font-weight:900; margin-top:.25rem; white-space:nowrap; }
            .ec-desc { color:#B8B8B8; font-size:1rem; margin-top:.35rem; overflow-wrap:break-word; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
            .ec-time { border-top:1px solid #6E665A; margin-top:1rem; padding-top:.75rem; display:flex; flex-wrap:wrap; gap:.65rem; color:#F2F2F2; font-weight:750; }
            .ec-menu-legend { display:flex; flex-wrap:wrap; gap:.8rem; border:1px solid #2A2A2A; border-radius:14px; background:linear-gradient(180deg, #121212, #0D0D0D); padding:.85rem 1rem; margin:1.1rem 0; color:#B8B8B8; }
            .ec-menu-legend strong { color:#fff; }
            .ec-panel { border:1px solid #2A2A2A; border-radius:18px; background:linear-gradient(180deg, #121212, #0D0D0D); padding:1rem; position:sticky; top:18px; }
            .ec-cart-line { border:1px solid #2A2A2A; border-radius:12px; padding:.7rem; margin-bottom:.6rem; background:#121212; }
            .ec-total { display:grid; grid-template-columns:1fr 1fr; gap:.6rem; margin:.8rem 0; }
            .ec-tile { border:1px solid #2A2A2A; border-radius:12px; padding:.75rem; background:#181818; }
            .ec-tile-label { color:#A8A8A8; font-size:.74rem; letter-spacing:.08em; text-transform:uppercase; }
            .ec-tile-value { margin-top:.25rem; font-size:1.2rem; font-weight:850; }
            .stButton > button { border-radius:12px; font-weight:750; border:1px solid #2A2A2A; background:#181818; color:#fff; }
            .stButton > button[kind="primary"] { border-color:transparent; background:linear-gradient(90deg, #B8151B, #D71920); color:#fff; }
            @media (max-width: 1200px) { .ec-thumb { width:64px; height:64px; } .ec-name { font-size:1.25rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def timing_for(item: dict) -> tuple[float, float]:
    name = str(item.get("name") or "").lower()
    category = str(item.get("category") or "").lower()
    desc = str(item.get("description") or "").lower()
    text = f"{name} {desc}"
    if category == "drinks":
        if "coke" in text or "can" in text:
            return 0.2, 0.0
        if "lemonade" in text or "fresh" in text:
            return 1.3, 0.0
        if "horchata" in text:
            return 0.7, 0.0
        return 0.5, 0.0
    if "guacamole" in text:
        return 2.2, 0.0
    if "nachos" in text:
        return 1.5, 3.2
    if category == "burritos":
        return (2.7, 6.3) if "carne" in text or "steak" in text else (2.5, 5.2)
    if category == "tacos":
        return (1.3, 3.7) if "carne" in text or "steak" in text else (1.2, 3.0)
    return 1.0, 3.0


def item_emoji(item: dict) -> str:
    category = str(item.get("category") or "").lower()
    name = str(item.get("name") or "").lower()
    if category == "drinks":
        return "🥤"
    if category == "burritos":
        return "🌯"
    if category == "tacos":
        return "🌮"
    if category == "sides" or "guacamole" in name:
        return "🥑"
    return "🍽️"


def badges_for(item: dict) -> str:
    badges = []
    name = str(item.get("name") or "")
    if name in HEALTHY_ITEM_NAMES:
        badges.append("<span class='ec-badge healthy'>🥬 Healthy</span>")
    if name in SPECIALTY_ITEM_NAMES:
        badges.append("<span class='ec-badge specialty'>⭐ Specialty</span>")
    return "".join(badges)


def cart_total() -> float:
    return sum(c["price"] * c["quantity"] for c in st.session_state.cart)


def wait_time(menu_lookup: dict[int, dict]) -> float:
    if not st.session_state.cart:
        return 0.0
    durations = []
    for line in st.session_state.cart:
        item = menu_lookup.get(line["menu_id"])
        if not item:
            continue
        prep, cook = timing_for(item)
        per = prep + cook
        qty = max(int(line.get("quantity") or 1), 1)
        durations.append(per + max(0, qty - 1) * per * 0.6)
    return round(max(durations) + 2, 1) if durations else 0.0


def add_to_cart(menu_item: dict, qty: int = 1) -> None:
    for c in st.session_state.cart:
        if c["menu_id"] == menu_item["id"] and not c.get("notes"):
            c["quantity"] += qty
            return
    st.session_state.cart.append({
        "menu_id": menu_item["id"],
        "name": menu_item["name"],
        "price": menu_item["price"],
        "quantity": qty,
        "notes": None,
    })


def remove_line(idx: int) -> None:
    if 0 <= idx < len(st.session_state.cart):
        st.session_state.cart.pop(idx)


def render_menu_card(item: dict) -> None:
    prep, cook = timing_for(item)
    cook_label = "No cook" if cook <= 0 else f"Cook {cook:.1f}m"
    st.markdown(
        f"""
        <div class='ec-menu-card'>
          <div class='ec-card-head'>
            <div class='ec-thumb'>{item_emoji(item)}</div>
            <div class='ec-card-body'>
              <div class='ec-badges'>{badges_for(item)}</div>
              <div class='ec-name'>{escape(str(item['name']))}</div>
              <div class='ec-price'>${float(item['price']):.2f}</div>
              <div class='ec-desc'>{escape(str(item.get('description') or ''))}</div>
            </div>
          </div>
          <div class='ec-time'><span>◷ Prep {prep:.1f}m</span><span>|</span><span>◶ {cook_label}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("＋ Add to Order", key=f"add_{item['id']}", type="primary", width="stretch"):
        add_to_cart(item)
        st.rerun()


def render_section(title: str, icon: str, items: list[dict], columns: int) -> None:
    st.markdown(
        f"""
        <div class='ec-section-row'>
          <div style='font-size:1.2rem'>{escape(icon)}</div>
          <div class='ec-section-title'>{escape(title)}</div>
          <div class='ec-section-divider'></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(columns)
    for idx, item in enumerate(items):
        with cols[idx % columns]:
            render_menu_card(item)


apply_order_theme()
menu = orders_mod.get_menu()
menu_lookup = {m["id"]: m for m in menu}
by_category: dict[str, list[dict]] = defaultdict(list)
for item in menu:
    by_category[str(item.get("category") or "other").lower()].append(item)

left, right = st.columns([2.2, 1], gap="large")

with left:
    st.markdown("<div class='ec-title'>Order Station</div><div class='ec-hero'>Customer Order</div><div class='ec-sub'>Tap menu items or use voice. Live timing keeps the line moving.</div>", unsafe_allow_html=True)
    for category in ["burritos", "drinks", "tacos", "sides"]:
        items = by_category.get(category, [])
        if items:
            title, icon, columns = CATEGORY_UI[category]
            render_section(title, icon, items, columns)
    st.markdown(
        """
        <div class='ec-menu-legend'>
          <strong>Menu symbols:</strong>
          <span>🥬 Healthy: lighter option picked by the truck</span>
          <span>⭐ Specialty: house specialty or signature item</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.markdown("<div class='ec-panel'>", unsafe_allow_html=True)
    st.subheader("🛒 Cart")
    if not st.session_state.cart:
        st.info("Cart is empty.")
    else:
        for idx, line in enumerate(st.session_state.cart):
            st.markdown("<div class='ec-cart-line'>", unsafe_allow_html=True)
            top = st.columns([3, 1])
            with top[0]:
                st.markdown(f"**{line['quantity']}× {escape(line['name'])}**")
                if line.get("notes"):
                    st.caption(f"📝 {line['notes']}")
            with top[1]:
                st.markdown(f"${line['price'] * line['quantity']:.2f}")
            qcol = st.columns([1, 1, 1])
            with qcol[0]:
                if st.button("−", key=f"dec_{idx}"):
                    line["quantity"] = max(0, line["quantity"] - 1)
                    if line["quantity"] == 0:
                        remove_line(idx)
                    st.rerun()
            with qcol[1]:
                if st.button("+", key=f"inc_{idx}"):
                    line["quantity"] += 1
                    st.rerun()
            with qcol[2]:
                if st.button("✕", key=f"del_{idx}"):
                    remove_line(idx)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    wait = wait_time(menu_lookup)
    st.markdown(
        "<div class='ec-total'>"
        f"<div class='ec-tile'><div class='ec-tile-label'>Total</div><div class='ec-tile-value'>${cart_total():.2f}</div></div>"
        f"<div class='ec-tile'><div class='ec-tile-label'>Est Wait</div><div class='ec-tile-value'>{wait:.1f}m</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.subheader("🎙️ Edit by Voice")
    audio = st.audio_input("Record")
    if audio is not None:
        with st.spinner("Listening..."):
            try:
                transcript = agents.transcribe_audio(audio.read(), filename="input.wav")
            except Exception as exc:
                st.error(f"Transcription failed: {exc}")
                transcript = None
        if transcript:
            st.markdown(f"**You said:** _{transcript}_")
            with st.spinner("Updating cart..."):
                try:
                    parsed = agents.parse_voice_order(transcript, st.session_state.cart)
                    st.session_state.cart = agents.apply_actions_to_cart(st.session_state.cart, parsed.get("actions", []))
                    st.session_state.voice_log.append({"transcript": transcript, "reply": parsed.get("reply", "")})
                    if parsed.get("reply"):
                        st.success(parsed["reply"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Couldn't process that: {exc}")

    st.markdown("---")
    name = st.text_input("Your name (for the order)", value="", placeholder="e.g. Maria")
    phone = st.text_input("Phone for SMS updates (optional)", value="", placeholder="e.g. +15551234567")
    can_checkout = bool(st.session_state.cart) and bool(name.strip())
    if st.button("Place Order & Pay", type="primary", width="stretch", disabled=not can_checkout):
        payload = [{"menu_id": c["menu_id"], "quantity": c["quantity"], "notes": c.get("notes")} for c in st.session_state.cart]
        with st.spinner("Charging card..."):
            result = orders_mod.create_order(payload, customer_name=name.strip(), phone=phone.strip() or None)
        if result.get("ok"):
            st.success(f"Order #{result['order_id']} placed · Total ${result['total']:.2f} · Est wait {wait:.1f}m")
            st.balloons()
            st.session_state.cart = []
            st.session_state.voice_log = []
            st.rerun()
        else:
            st.error(f"Order failed: {result.get('error', 'unknown')}")
            if result.get("missing_ingredients"):
                st.caption(f"Missing: {', '.join(result['missing_ingredients'])}")
    st.markdown("</div>", unsafe_allow_html=True)
