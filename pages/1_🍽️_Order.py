"""Customer order kiosk view."""
from __future__ import annotations

import html
import math
from collections import defaultdict
from datetime import date
from urllib.parse import urlencode

import _path_setup  # noqa: F401
import streamlit as st

from backend import agents, analytics, config, macros, nutrition, orders
from backend.autopilot import log_agent_event
from backend.bootstrap import ensure_app_ready
from backend.ui_components import (
    CUSTOMER_PAGE_STATUS,
    VIEW_CUSTOMER,
    enforce_view_mode,
    render_app_shell,
)


st.set_page_config(page_title="Customer Order — El Camino", page_icon="🍽️", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_CUSTOMER)
enforce_view_mode(VIEW_CUSTOMER)


MENU_IMAGE_OVERRIDES = {
    "Carne Burrito": "https://unsplash.com/photos/p-O37cSAV_4/download?force=true",
    "Veggie Burrito": "https://unsplash.com/photos/qYtfN2109Wg/download?force=true",
    "Carne Asada Taco": "https://unsplash.com/photos/_j4S4V2C8ew/download?force=true",
    "Al Pastor Taco": "https://unsplash.com/photos/wIqpmuOloVA/download?force=true",
    "Veggie Taco": "https://unsplash.com/photos/lP5MCM6nZ5A/download?force=true",
    "Chips & Guacamole": "https://images.pexels.com/photos/7601338/pexels-photo-7601338.jpeg?auto=compress&cs=tinysrgb&w=1100",
    "Loaded Nachos": "https://images.pexels.com/photos/27603312/pexels-photo-27603312.jpeg?auto=compress&cs=tinysrgb&w=1100",
    "Coke": "https://images.pexels.com/photos/14650671/pexels-photo-14650671.jpeg?auto=compress&cs=tinysrgb&w=1100",
    "Lemonade": "https://images.pexels.com/photos/2109099/pexels-photo-2109099.jpeg?auto=compress&cs=tinysrgb&w=1100",
    "Horchata": "https://images.pexels.com/photos/5946963/pexels-photo-5946963.jpeg?auto=compress&cs=tinysrgb&w=1100",
}

CATEGORIES = ["Popular", "Burritos", "Tacos", "Sides", "Drinks"]


cfg = config.get_business_config()
menu_rows = orders.get_menu(only_available=False)
menu_by_id = {item["id"]: item for item in menu_rows}
menu_by_name = {item["name"]: item for item in menu_rows}
open_now = str(cfg.get("openStatus", "open")).lower() in {"open", "1", "true", "yes", "on"}

if "cart" not in st.session_state:
    starter_cart: list[dict] = []
    for name in ("Carne Burrito", "Al Pastor Taco", "Chips & Guacamole"):
        item = menu_by_name.get(name)
        if item:
            starter_cart.append(
                {
                    "menu_id": item["id"],
                    "name": item["name"],
                    "price": float(item["price"]),
                    "quantity": 1,
                    "notes": None,
                }
            )
    st.session_state.cart = starter_cart
if "last_order_confirmation" not in st.session_state:
    st.session_state.last_order_confirmation = None


def _safe(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _image_url(item: dict | None) -> str:
    if not item:
        return ""
    return str(item.get("image_url") or MENU_IMAGE_OVERRIDES.get(str(item.get("name")), ""))


def _timing(item: dict) -> tuple[float, float]:
    prep = float(item.get("prep_time_minutes") or 1)
    cook = float(item.get("cook_time_minutes") or 0)
    return prep, cook


def _cart_total() -> float:
    return sum(float(line["price"]) * int(line["quantity"]) for line in st.session_state.cart)


def _cart_macro_totals() -> dict:
    return nutrition.calculate_cart_nutrition(st.session_state.cart)


def _selected_profile() -> dict | None:
    customer_id = st.session_state.get("selected_customer_id")
    if not customer_id:
        return None
    return macros.get_customer_profile(int(customer_id))


def _cart_wait_minutes() -> float:
    durations: list[float] = []
    for line in st.session_state.cart:
        item = menu_by_id.get(line["menu_id"])
        if not item:
            continue
        prep, cook = _timing(item)
        per = prep + cook
        qty = max(1, int(line["quantity"]))
        durations.append(per + max(0, qty - 1) * (per * 0.6))
    buffer_minutes = float(cfg.get("defaultPrepBufferMinutes", 2) or 2)
    return round((max(durations) if durations else 9) + buffer_minutes, 1)


def _add_item(item: dict) -> None:
    for line in st.session_state.cart:
        if line["menu_id"] == item["id"] and not line.get("notes"):
            line["quantity"] += 1
            return
    st.session_state.cart.append(
        {
            "menu_id": item["id"],
            "name": item["name"],
            "price": float(item["price"]),
            "quantity": 1,
            "notes": None,
        }
    )


def _remove_line(index: int) -> None:
    if 0 <= index < len(st.session_state.cart):
        st.session_state.cart.pop(index)


def _adjust_line(index: int, delta: int) -> None:
    if not 0 <= index < len(st.session_state.cart):
        return
    new_qty = int(st.session_state.cart[index]["quantity"]) + delta
    if new_qty <= 0:
        _remove_line(index)
        return
    st.session_state.cart[index]["quantity"] = min(new_qty, 9)


def _checkout(customer_name: str) -> None:
    if not open_now:
        st.error("Ordering is currently closed.")
        return
    if not st.session_state.cart:
        st.error("Your cart is empty.")
        return

    result = orders.create_order(
        cart=st.session_state.cart,
        customer_name=(customer_name.strip() or "Guest"),
        source="customer_view",
        customer_id=st.session_state.get("selected_customer_id"),
        track_macros=bool(st.session_state.get("track_order_macros")),
    )
    if not result.get("ok"):
        st.error(f"Could not place order: {result.get('error')}")
        return

    st.session_state.last_order_confirmation = result
    st.session_state.cart = []
    log_agent_event(
        "Customer Agent",
        "healthy",
        "Customer placed order",
        f"Order {result['order_number']} placed from customer view.",
        "Track Order",
    )
    if result.get("macro_log"):
        log_agent_event(
            "Customer Macro Agent",
            "healthy",
            "Order macro logged",
            f"Order {result['order_number']} updated the customer macro log.",
            "Macro Log",
        )


def _active_category() -> str:
    category = st.query_params.get("category", CATEGORIES[0])
    if isinstance(category, list):
        category = category[0] if category else CATEGORIES[0]
    return category if category in CATEGORIES else CATEGORIES[0]


def _href(**updates: object) -> str:
    params = {"category": _active_category()}
    params.update({key: value for key, value in updates.items() if value is not None})
    return "/Order?" + urlencode(params)


def _handle_query_action() -> None:
    params = st.query_params
    action = params.get("cart_action")
    if isinstance(action, list):
        action = action[0] if action else None
    if not action:
        return

    try:
        if action == "add":
            menu_id = int(params.get("menu_id", 0))
            item = menu_by_id.get(menu_id)
            if item and bool(item.get("available", 1)):
                _add_item(item)
        elif action in {"inc", "dec", "remove"}:
            line_index = int(params.get("line", -1))
            if action == "inc":
                _adjust_line(line_index, 1)
            elif action == "dec":
                _adjust_line(line_index, -1)
            else:
                _remove_line(line_index)
    except (TypeError, ValueError):
        pass

    selected = _active_category()
    st.query_params.clear()
    st.query_params["category"] = selected
    st.rerun()


def _apply_order_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --order-bg: #070a0b;
                --order-panel: rgba(21, 22, 23, .88);
                --order-panel-2: rgba(18, 19, 20, .94);
                --order-line: rgba(255,255,255,.11);
                --order-line-soft: rgba(255,255,255,.07);
                --order-text: #f7f1e7;
                --order-muted: #b9b4ad;
                --order-red: #d54032;
                --order-red-dark: #8c211a;
                --order-green: #50d25e;
                --order-orange: #ed7148;
                --order-gold: #f6ad2f;
            }
            .main > div {
                max-width: none;
                padding-top: 1.1rem;
                padding-left: 2rem;
                padding-right: 1.6rem;
            }
            .stApp {
                background:
                    radial-gradient(circle at 54% -8%, rgba(255,255,255,.08), transparent 22%),
                    radial-gradient(circle at 76% 11%, rgba(196,63,49,.12), transparent 17%),
                    linear-gradient(180deg, #080b0d 0%, #050708 100%) !important;
            }
            [data-testid="stSidebar"] {
                width: 292px !important;
                min-width: 292px !important;
                background:
                    radial-gradient(circle at 50% 3%, rgba(214,136,79,.18), transparent 18%),
                    linear-gradient(180deg, #0a0d0f 0%, #050708 100%) !important;
                border-right: 1px solid rgba(255,255,255,.12);
            }
            [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                gap: .55rem;
            }
            [data-testid="stSidebar"] h2 {
                font-family: Georgia, "Times New Roman", serif !important;
                letter-spacing: .28em;
                text-align: center;
                font-size: 1.6rem;
                line-height: 1.05;
                margin: .8rem 0 0;
            }
            [data-testid="stSidebar"] p {
                text-align: center;
                letter-spacing: .32em;
                text-transform: uppercase;
                color: #c7b9a3 !important;
                font-size: .72rem;
            }
            [data-testid="stSidebar"] .stPageLink a,
            [data-testid="stSidebar"] a {
                border-radius: 8px;
                color: #bebbb6 !important;
                min-height: 42px;
                font-weight: 620;
            }
            [data-testid="stSidebar"] .stPageLink a[aria-current="page"] {
                background: linear-gradient(180deg, #d64b3e, #9f261f) !important;
                color: #fff !important;
                box-shadow: inset 0 1px rgba(255,255,255,.22);
            }
            div[data-testid="stRadio"] {
                border: 1px solid var(--order-line);
                border-radius: 14px;
                padding: .55rem .75rem;
                background: rgba(255,255,255,.045);
                margin-top: .8rem;
            }
            .order-top {
                display: grid;
                grid-template-columns: minmax(280px, 1fr) 234px 234px 220px;
                gap: 22px;
                align-items: start;
                margin-bottom: 26px;
            }
            .order-title h1 {
                margin: 0;
                color: var(--order-text);
                font-family: Georgia, "Times New Roman", serif;
                font-size: clamp(3rem, 4.3vw, 4.55rem);
                line-height: .9;
                letter-spacing: -.01em;
                font-weight: 800;
            }
            .order-title p {
                margin: .72rem 0 0;
                color: var(--order-text);
                font-size: 1.24rem;
                font-weight: 500;
            }
            .status-tile, .track-tile, .stats-strip, .menu-card, .cart-shell, .cart-total {
                border: 1px solid var(--order-line);
                background: linear-gradient(145deg, rgba(30,31,32,.88), rgba(15,16,17,.92));
                box-shadow: inset 0 1px rgba(255,255,255,.05), 0 18px 42px rgba(0,0,0,.22);
            }
            .status-tile {
                border-radius: 14px;
                padding: 20px 22px;
                min-height: 112px;
            }
            .status-row {
                display: flex;
                align-items: center;
                gap: 10px;
                color: var(--order-green);
                font-weight: 820;
                letter-spacing: .04em;
            }
            .status-dot, .avail-dot {
                width: 13px;
                height: 13px;
                border-radius: 50%;
                background: var(--order-green);
                box-shadow: 0 0 18px rgba(80,210,94,.5);
                display: inline-block;
                flex: 0 0 auto;
            }
            .tile-kicker {
                text-transform: uppercase;
                color: var(--order-muted);
                font-size: .83rem;
                font-weight: 820;
                letter-spacing: .04em;
            }
            .wait-value {
                display: flex;
                align-items: baseline;
                gap: 16px;
                margin-top: 6px;
            }
            .wait-value strong {
                font-size: 1.9rem;
                line-height: 1;
            }
            .wait-value span, .status-tile p {
                color: #dad5cc;
                margin: 12px 0 0;
            }
            .track-tile {
                min-height: 88px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 14px;
                border-color: rgba(237,113,72,.85);
                border-radius: 15px;
                color: #f6f1ea;
                font-size: 1.08rem;
                font-weight: 790;
                text-decoration: none !important;
            }
            .stats-strip {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                border-radius: 10px;
                padding: 18px 18px;
                margin-bottom: 26px;
            }
            .stat-cell {
                display: grid;
                grid-template-columns: 56px 1fr;
                gap: 14px;
                align-items: center;
                padding: 0 20px;
                border-right: 1px dashed rgba(255,255,255,.16);
            }
            .stat-cell:last-child { border-right: 0; }
            .stat-icon {
                width: 54px;
                height: 54px;
                display: grid;
                place-items: center;
                border-radius: 50%;
                background: rgba(255,255,255,.08);
                color: #f8efe0;
            }
            .stat-cell:nth-child(1) .stat-icon { background: rgba(99,58,38,.82); }
            .stat-cell:nth-child(3) .stat-icon { color: var(--order-orange); background: rgba(237,113,72,.14); }
            .stat-cell:nth-child(4) .stat-icon { color: var(--order-gold); background: rgba(246,173,47,.12); }
            .stat-label {
                color: #c8c1b8;
                font-size: .92rem;
                margin-bottom: 2px;
            }
            .stat-value {
                color: #fffaf2;
                font-size: 1.35rem;
                font-weight: 850;
            }
            .category-tabs {
                display: flex;
                gap: 18px;
                border-bottom: 1px solid var(--order-line);
                margin: 0 0 20px;
                padding-bottom: 10px;
            }
            .category-tabs a {
                color: #d0cac2;
                text-decoration: none !important;
                padding: 10px 18px;
                border-radius: 10px;
                font-weight: 750;
            }
            .category-tabs a.active {
                color: #fff;
                background: linear-gradient(180deg, #dd5447, #b62d25);
            }
            .menu-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 20px;
            }
            .menu-card {
                border-radius: 11px;
                overflow: hidden;
                min-height: 316px;
                position: relative;
            }
            .menu-card img {
                width: 100%;
                height: 126px;
                object-fit: cover;
                display: block;
                filter: saturate(1.08) contrast(1.04);
            }
            .menu-card .body {
                padding: 14px 16px 14px;
            }
            .menu-line {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: start;
            }
            .menu-line h3 {
                margin: 0;
                font-size: 1.18rem;
                line-height: 1.16;
                font-weight: 850;
                color: #fffaf2;
            }
            .price {
                color: #fffaf2;
                font-size: 1.18rem;
                font-weight: 850;
                white-space: nowrap;
            }
            .desc {
                color: #d1cbc3;
                font-size: .94rem;
                line-height: 1.32;
                min-height: 40px;
                margin: 10px 0 9px;
            }
            .timing, .available, .cart-note, .secure {
                color: #c9c2ba;
                font-size: .86rem;
            }
            .available {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-top: 14px;
            }
            .add-link {
                position: absolute;
                right: 16px;
                bottom: 13px;
                min-width: 72px;
                text-align: center;
                color: #fff !important;
                text-decoration: none !important;
                font-weight: 840;
                border-radius: 7px;
                padding: 9px 16px;
                background: linear-gradient(180deg, #d24c40, #a92b24);
                box-shadow: inset 0 1px rgba(255,255,255,.18);
            }
            .add-link.disabled {
                opacity: .42;
                pointer-events: none;
            }
            .cart-shell {
                border-radius: 9px;
                padding: 20px 20px 18px;
                min-height: 760px;
            }
            .cart-title {
                display: flex;
                gap: 14px;
                align-items: center;
                margin-bottom: 20px;
                font-size: 1.1rem;
                font-weight: 850;
            }
            .cart-row {
                display: grid;
                grid-template-columns: 76px minmax(100px, 1fr) 126px 30px;
                gap: 14px;
                align-items: center;
                padding: 12px 6px;
                border: 1px solid var(--order-line-soft);
                border-radius: 8px;
                margin-bottom: 10px;
                background: rgba(10,11,12,.3);
            }
            .cart-row img {
                width: 70px;
                height: 64px;
                object-fit: cover;
                border-radius: 8px;
            }
            .cart-item-name {
                font-weight: 850;
                color: #fffaf2;
                margin-bottom: 3px;
            }
            .cart-controls {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                align-items: center;
                border: 1px solid var(--order-line);
                border-radius: 7px;
                min-height: 43px;
            }
            .cart-controls a {
                color: #eee8de !important;
                text-decoration: none !important;
                text-align: center;
                font-size: 1.15rem;
            }
            .cart-controls span {
                text-align: center;
                color: #fff;
                font-weight: 850;
            }
            .trash {
                color: var(--order-red) !important;
                text-decoration: none !important;
                font-size: 1.24rem;
            }
            .cart-instructions {
                display: flex;
                gap: 10px;
                align-items: center;
                color: #c7c0b8;
                margin: 20px 2px 18px;
                font-size: .91rem;
            }
            .cart-total {
                border-radius: 8px;
                padding: 18px 20px;
                margin-bottom: 14px;
            }
            .macro-mini {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 8px;
                margin: 14px 0;
            }
            .macro-mini div {
                border: 1px solid var(--order-line-soft);
                border-radius: 7px;
                padding: 9px 8px;
                background: rgba(255,255,255,.035);
            }
            .macro-mini span {
                display: block;
                color: var(--order-muted);
                font-size: .72rem;
                text-transform: uppercase;
                letter-spacing: .04em;
            }
            .macro-mini strong {
                display: block;
                color: #fffaf2;
                font-size: .92rem;
                margin-top: 2px;
            }
            .total-row {
                display: flex;
                justify-content: space-between;
                color: #d2ccc4;
                margin-bottom: 12px;
            }
            .total-main {
                display: flex;
                justify-content: space-between;
                border-top: 1px solid var(--order-line-soft);
                border-bottom: 1px solid var(--order-line-soft);
                padding: 16px 0;
                margin: 4px 0 14px;
                font-size: 1.2rem;
                font-weight: 900;
            }
            .total-main strong:last-child { color: var(--order-red); }
            .wait-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: #d2ccc4;
                font-size: .94rem;
            }
            .cart-empty {
                color: var(--order-muted);
                border: 1px dashed var(--order-line);
                border-radius: 8px;
                padding: 18px;
                margin-bottom: 18px;
            }
            div[data-baseweb="input"] > div {
                border-radius: 7px !important;
                min-height: 45px;
                background: rgba(255,255,255,.08) !important;
                border-color: rgba(255,255,255,.11) !important;
            }
            .stButton > button[kind="primary"] {
                min-height: 60px;
                border-radius: 7px;
                font-size: 1.1rem;
                background: linear-gradient(180deg, #df5246, #bc2f27) !important;
                border: 0 !important;
            }
            .secure {
                text-align: center;
                margin-top: 12px;
            }
            @media (max-width: 1200px) {
                .order-top { grid-template-columns: 1fr 1fr; }
                .menu-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .stats-strip { grid-template-columns: repeat(2, 1fr); gap: 14px; }
                .stat-cell { border-right: 0; }
            }
            @media (max-width: 760px) {
                .order-top, .menu-grid { grid-template-columns: 1fr; }
                .category-tabs { overflow-x: auto; }
                .cart-row { grid-template-columns: 64px 1fr; }
                .cart-controls, .trash { grid-column: 2; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _icon(name: str) -> str:
    icons = {
        "bag": "<svg width='23' height='23' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8'><path d='M6 7h12l1 14H5L6 7Z'/><path d='M9 7a3 3 0 0 1 6 0'/></svg>",
        "clock": "<svg width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8'><circle cx='12' cy='12' r='9'/><path d='M12 7v5l3.5 2.2'/></svg>",
        "flame": "<svg width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.9'><path d='M12 21c3.8 0 6.5-2.6 6.5-6.2 0-2.9-1.7-5.3-4.2-7.9.1 2.2-.7 3.5-2.3 4.3.2-3-1.1-5.5-3.8-8.2.2 4.1-2.7 6.1-2.7 10.7C5.5 18 8.2 21 12 21Z'/></svg>",
        "star": "<svg width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.9'><path d='m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 16.9 6.6 19.8l1-6.1-4.4-4.3 6.1-.9L12 3Z'/></svg>",
        "pin": "<svg width='25' height='25' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8'><path d='M12 21s7-5.7 7-12A7 7 0 0 0 5 9c0 6.3 7 12 7 12Z'/><circle cx='12' cy='9' r='2.2'/></svg>",
        "note": "<svg width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8'><path d='M14 3v4a2 2 0 0 0 2 2h4'/><path d='M5 21h10l5-5V7l-4-4H5v18Z'/><path d='M9 14h6'/></svg>",
        "lock": "<svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.9'><rect x='5' y='11' width='14' height='10' rx='2'/><path d='M8 11V8a4 4 0 0 1 8 0v3'/></svg>",
    }
    return icons[name]


def _render_header(wait_minutes: float) -> None:
    open_label = "OPEN" if open_now else "CLOSED"
    open_copy = "We're ready to serve you" if open_now else "Ordering is currently paused"
    status_color = "var(--order-green)" if open_now else "var(--order-red)"
    st.markdown(
        f"""
        <div class="order-top">
            <div class="order-title">
                <h1>Order Food</h1>
                <p>Fresh food, fast pickup.</p>
            </div>
            <div class="status-tile">
                <div class="status-row" style="color:{status_color};">
                    <span class="status-dot" style="background:{status_color};"></span>{open_label}
                </div>
                <p>{open_copy}</p>
            </div>
            <div class="status-tile">
                <div class="tile-kicker">EST. WAIT TIME</div>
                <div class="wait-value"><strong>{int(round(wait_minutes))}</strong><span>min</span></div>
                <p>Updated just now</p>
            </div>
            <a class="track-tile" href="/Order_Status">
                {_icon("pin")} <span>Track Order</span>
            </a>
        </div>
        <div class="stats-strip">
            <div class="stat-cell">
                <div class="stat-icon">{_icon("bag")}</div>
                <div><div class="stat-label">Today's Orders</div><div class="stat-value">128</div></div>
            </div>
            <div class="stat-cell">
                <div class="stat-icon">{_icon("clock")}</div>
                <div><div class="stat-label">Avg. Wait Time</div><div class="stat-value">10.2 <span style="font-size:.86rem;font-weight:500;">min</span></div></div>
            </div>
            <div class="stat-cell">
                <div class="stat-icon">{_icon("flame")}</div>
                <div><div class="stat-label">Items Sold</div><div class="stat-value">342</div></div>
            </div>
            <div class="stat-cell">
                <div class="stat-icon">{_icon("star")}</div>
                <div><div class="stat-label">Customer Rating</div><div class="stat-value">4.8</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_categories(active: str) -> None:
    links = []
    for category in CATEGORIES:
        css = "active" if category == active else ""
        links.append(f'<a class="{css}" href="/Order?{urlencode({"category": category})}">{category}</a>')
    st.markdown(f'<div class="category-tabs">{"".join(links)}</div>', unsafe_allow_html=True)


def _render_menu_grid(items: list[dict]) -> None:
    if not items:
        st.markdown('<div class="cart-empty">No items in this category.</div>', unsafe_allow_html=True)
        return

    cards = []
    for item in items[:6]:
        available = bool(item.get("available", 1))
        prep, cook = _timing(item)
        image = _safe(_image_url(item))
        add_class = "" if available else " disabled"
        add_href = _href(cart_action="add", menu_id=item["id"]) if available else "#"
        cards.append(
            f'<article class="menu-card">'
            f'<img src="{image}" alt="{_safe(item["name"])}">'
            f'<div class="body">'
            f'<div class="menu-line">'
            f'<h3>{_safe(item["name"])}</h3>'
            f'<div class="price">${float(item["price"]):.2f}</div>'
            f'</div>'
            f'<div class="desc">{_safe(item.get("description"))}</div>'
            f'<div class="timing">◷ Prep {prep:.1f}m · Cook {cook:.1f}m</div>'
            f'<div class="available"><span class="avail-dot"></span>{"Available" if available else "Unavailable"}</div>'
            f'<a class="add-link{add_class}" href="{add_href}">Add</a>'
            f'</div>'
            f'</article>'
        )
    st.markdown(f'<div class="menu-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_cart(subtotal: float, tax: float, total: float, wait: float, cart_macros: dict, impact_summary: dict | None) -> None:
    rows = []
    if st.session_state.cart:
        for index, line in enumerate(st.session_state.cart):
            item = menu_by_id.get(line["menu_id"])
            image = _safe(_image_url(item))
            rows.append(
                f'<div class="cart-row">'
                f'<img src="{image}" alt="{_safe(line["name"])}">'
                f'<div>'
                f'<div class="cart-item-name">{_safe(line["name"])}</div>'
                f'<div class="timing">${float(line["price"]):.2f}</div>'
                f'</div>'
                f'<div class="cart-controls">'
                f'<a href="{_href(cart_action="dec", line=index)}">−</a>'
                f'<span>{int(line["quantity"])}</span>'
                f'<a href="{_href(cart_action="inc", line=index)}">+</a>'
                f'</div>'
                f'<a class="trash" href="{_href(cart_action="remove", line=index)}">⌫</a>'
                f'</div>'
            )
    else:
        rows.append('<div class="cart-empty">Pick items from the menu to begin your order.</div>')

    impact = ""
    if impact_summary:
        impact = (
            f'<div class="timing" style="margin-top:8px;">'
            f'After this order: {max(0, float(impact_summary.get("calories_remaining") or 0) - cart_macros["calories"]):.0f} cal, '
            f'{max(0, float(impact_summary.get("protein_remaining_g") or 0) - cart_macros["protein_g"]):.0f}g protein remaining'
            f'</div>'
        )

    st.markdown(
        (
            f'<div class="cart-shell">'
            f'<div class="cart-title">{_icon("bag")} <span>Your Cart</span></div>'
            f'{"".join(rows)}'
            f'<div class="cart-instructions">{_icon("note")} <span>Add a note or special instructions</span></div>'
            f'<div class="cart-total">'
            f'<div class="tile-kicker">This order macros</div>'
            f'<div class="macro-mini">'
            f'<div><span>Cal</span><strong>{cart_macros["calories"]:.0f}</strong></div>'
            f'<div><span>Protein</span><strong>{cart_macros["protein_g"]:.0f}g</strong></div>'
            f'<div><span>Carbs</span><strong>{cart_macros["carbs_g"]:.0f}g</strong></div>'
            f'<div><span>Fat</span><strong>{cart_macros["fat_g"]:.0f}g</strong></div>'
            f'</div>'
            f'{impact}'
            f'<div class="total-row"><span>Subtotal</span><strong>${subtotal:.2f}</strong></div>'
            f'<div class="total-row"><span>Tax</span><strong>${tax:.2f}</strong></div>'
            f'<div class="total-main"><strong>Total</strong><strong>${total:.2f}</strong></div>'
            f'<div class="wait-row"><span>{_icon("clock")} &nbsp; Estimated Wait</span><strong>{int(round(wait))} min</strong></div>'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )


def _close_cart() -> None:
    st.markdown(f'<div class="secure">{_icon("lock")} &nbsp; Secure checkout</div></div>', unsafe_allow_html=True)


_handle_query_action()
_apply_order_styles()

sales = analytics.sales_by_item(days=30)
popular_names = [row["name"] for row in sales[:6]]
if not popular_names:
    popular_names = ["Carne Burrito", "Coke", "Chips & Guacamole", "Loaded Nachos", "Al Pastor Taco", "Carne Asada Taco"]

by_category: dict[str, list[dict]] = defaultdict(list)
for item in menu_rows:
    by_category[str(item.get("category") or "other").lower()].append(item)

popular_items = [item for item in menu_rows if item["name"] in popular_names][:6]
category_map: dict[str, list[dict]] = {
    "Popular": popular_items,
    "Burritos": by_category.get("burritos", [])[:6],
    "Tacos": by_category.get("tacos", [])[:6],
    "Sides": by_category.get("sides", [])[:6],
    "Drinks": by_category.get("drinks", [])[:6],
}

wait = _cart_wait_minutes()
_render_header(wait)

menu_col, cart_col = st.columns([2.15, 1.08], gap="large")
active_category = _active_category()

with menu_col:
    _render_categories(active_category)
    _render_menu_grid(category_map.get(active_category, []))

with cart_col:
    subtotal = _cart_total()
    tax_rate = float(cfg.get("taxRate", 0.0825) or 0.0825)
    tax = math.floor(subtotal * tax_rate * 100) / 100
    total = round(subtotal + tax, 2)
    cart_macros = _cart_macro_totals()
    profile = _selected_profile()
    today_summary = macros.get_daily_macro_summary(profile["id"], date.today().isoformat()) if profile else None
    _render_cart(subtotal, tax, total, wait, cart_macros, today_summary)
    profiles = macros.list_customer_profiles()
    if profiles:
        labels = ["No macro profile"] + [f"{p['customer_name']} #{p['id']}" for p in profiles]
        selected_label = st.selectbox("Track macros for", labels, index=0)
        selected_profile = profiles[labels.index(selected_label) - 1] if selected_label != "No macro profile" else None
        st.session_state["selected_customer_id"] = selected_profile["id"] if selected_profile else None
    else:
        st.caption("Create a macro profile on the Macros page to track this order.")
        st.session_state["selected_customer_id"] = None
    st.session_state["track_order_macros"] = st.checkbox(
        "Track this order toward macros",
        value=bool(st.session_state.get("selected_customer_id")),
        disabled=not bool(st.session_state.get("selected_customer_id")),
    )
    customer_name = st.text_input("Your Name", value=(profile or {}).get("customer_name", ""), placeholder="e.g. Marco", label_visibility="visible")
    if st.button(f"Place Order   •   ${total:.2f}   →", type="primary", use_container_width=True):
        _checkout(customer_name)
        st.rerun()
    _close_cart()

    with st.expander("Voice Order (optional)", expanded=False):
        st.caption("Try: two carne tacos and a horchata.")
        voice_text = st.text_input("Voice command", placeholder="two carne tacos and a horchata")
        if st.button("Apply Voice Command", use_container_width=True):
            if not voice_text.strip():
                st.error("Enter a voice command first.")
            else:
                try:
                    parsed = agents.parse_voice_order(voice_text, st.session_state.cart)
                    st.session_state.cart = agents.apply_actions_to_cart(
                        st.session_state.cart,
                        parsed.get("actions", []),
                    )
                    st.success(parsed.get("reply") or "Updated cart.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Voice processing failed: {exc}")

if st.session_state.last_order_confirmation:
    confirm = st.session_state.last_order_confirmation
    st.markdown(
        f"""
        <div class="status-tile" style="margin-top:24px;">
            <div class="status-row"><span class="status-dot"></span>ORDER CONFIRMED</div>
            <p>Order {confirm["order_number"]} is received. Estimated ready: {confirm.get("estimated_ready_at") or "TBD"}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Track this order", use_container_width=False):
        st.session_state["order_lookup_default"] = confirm["order_number"]
        if hasattr(st, "switch_page"):
            st.switch_page(CUSTOMER_PAGE_STATUS)
