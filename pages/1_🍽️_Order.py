"""Customer kiosk order page with premium El Camino command-center UI."""
from __future__ import annotations

import _path_setup  # noqa: F401
from collections import defaultdict
from html import escape

import streamlit as st

from backend import agents, orders as orders_mod
from backend import config as config_mod
from backend import inventory as inventory_mod
from backend.bootstrap import ensure_app_ready
from backend.timing import estimate_menu_timing, has_placeholder_timing


st.set_page_config(page_title="Order — EL CAMINO", page_icon="🛣️", layout="wide")
ensure_app_ready()


EL_CAMINO_THEME = {
    "page_bg": "#070707",
    "sidebar_bg": "#0B0B0B",
    "card_bg": "#111111",
    "card_bg_elevated": "#191919",
    "text_primary": "#FFFFFF",
    "text_secondary": "#A8A8A8",
    "text_muted": "#6F6F6F",
    "border": "#2A2A2A",
    "red_primary": "#D71920",
    "red_hover": "#F12A32",
    "red_dark": "#7A1014",
    "success": "#22C55E",
    "warning": "#F59E0B",
}


CATEGORY_UI = {
    "burritos": {"title": "Burritos", "icon": "◔", "compact": False, "columns": 2},
    "drinks": {"title": "Drinks", "icon": "◫", "compact": True, "columns": 3},
    "tacos_sides": {"title": "Tacos & Sides", "icon": "◒", "compact": True, "columns": 3},
}


NAV_ITEMS = [
    ("Order", "◻", "pages/1_🍽️_Order.py", True),
    ("Kitchen", "◳", "pages/2_👨‍🍳_Kitchen.py", False),
    ("Inventory", "◫", "pages/3_📦_Inventory.py", False),
    ("Sales", "◱", "pages/4_📊_Sales.py", False),
    ("Revenue", "◍", "pages/5_💰_Revenue.py", False),
    ("Assistant", "✦", "pages/6_🤖_Assistant.py", False),
    ("Settings", "⚙", "pages/7_⚙️_Settings.py", False),
    ("Purchasing", "◬", "pages/8_🛒_Purchasing.py", False),
    ("Order Status", "◷", "pages/9_🔎_Order_Status.py", False),
]


if "cart" not in st.session_state:
    st.session_state.cart = []
if "voice_log" not in st.session_state:
    st.session_state.voice_log = []


# -----------------------------------------------------------------------------
# Theme and UI helpers
# -----------------------------------------------------------------------------

def apply_el_camino_theme() -> None:
    t = EL_CAMINO_THEME
    st.markdown(
        f"""
        <style>
            :root {{
                --ec-page-bg: {t['page_bg']};
                --ec-sidebar-bg: {t['sidebar_bg']};
                --ec-card: {t['card_bg']};
                --ec-card-elev: {t['card_bg_elevated']};
                --ec-text: {t['text_primary']};
                --ec-text-secondary: {t['text_secondary']};
                --ec-text-muted: {t['text_muted']};
                --ec-border: {t['border']};
                --ec-red: {t['red_primary']};
                --ec-red-hover: {t['red_hover']};
                --ec-red-dark: {t['red_dark']};
                --ec-success: {t['success']};
                --ec-warning: {t['warning']};
                --ec-radius: 16px;
            }}

            #MainMenu {{ visibility: hidden; }}
            footer {{ visibility: hidden; }}
            header[data-testid="stHeader"] {{
                background: transparent;
                height: 0;
            }}
            [data-testid="collapsedControl"] {{ display: none; }}

            .stApp {{
                background: radial-gradient(circle at 40% 0%, #0D0D0D 0%, var(--ec-page-bg) 36%);
                color: var(--ec-text);
                font-family: "Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
            }}

            .main > div {{
                padding-top: 1.0rem;
                padding-left: 0.8rem;
                padding-right: 0.8rem;
            }}

            h1, h2, h3, h4, h5, p, span, label, li, div {{
                color: var(--ec-text);
                font-family: "Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
            }}

            [data-testid="stSidebar"] {{
                width: 278px !important;
                min-width: 278px !important;
                max-width: 278px !important;
                background: linear-gradient(180deg, var(--ec-sidebar-bg) 0%, #070707 100%);
                border-right: 1px solid var(--ec-border);
            }}

            [data-testid="stSidebarNav"] {{
                display: none;
            }}

            [data-testid="stSidebar"] .block-container {{
                padding-top: 0.8rem;
                padding-left: 0.9rem;
                padding-right: 0.9rem;
                height: calc(100vh - 1rem);
            }}

            .ec-brand {{
                padding: 0.9rem 0.3rem 1rem 0.3rem;
                border-bottom: 1px solid var(--ec-border);
                margin-bottom: 0.9rem;
            }}
            .ec-brand-title {{
                letter-spacing: 0.14em;
                font-size: 2.0rem;
                font-weight: 800;
                line-height: 1;
                color: var(--ec-text);
            }}
            .ec-brand-sub {{
                margin-top: 0.42rem;
                color: var(--ec-red);
                font-size: 0.88rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                font-weight: 700;
            }}
            .ec-brand-tagline {{
                margin-top: 0.7rem;
                color: var(--ec-text-secondary);
                font-size: 0.93rem;
            }}

            .ec-nav-item {{
                display: flex;
                align-items: center;
                gap: 0.7rem;
                padding: 0.72rem 0.8rem;
                border-radius: 12px;
                border: 1px solid transparent;
                margin-bottom: 0.34rem;
                color: var(--ec-text-secondary);
                font-size: 1.02rem;
                transition: all .18s ease;
            }}
            .ec-nav-item.active {{
                background: linear-gradient(135deg, var(--ec-red-dark), #A0151B);
                color: var(--ec-text);
                border-color: rgba(255,255,255,0.08);
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
            }}
            .ec-nav-icon {{
                width: 18px;
                color: var(--ec-text-secondary);
                font-size: 0.95rem;
                text-align: center;
            }}
            .ec-nav-item.active .ec-nav-icon {{ color: var(--ec-text); }}

            [data-testid="stSidebar"] a[data-testid^="stPageLink"],
            [data-testid="stSidebar"] div[data-testid="stPageLink"] a,
            [data-testid="stSidebar"] a[kind="secondary"] {{
                text-decoration: none !important;
                color: var(--ec-text-secondary) !important;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 12px;
                padding: 0.72rem 0.8rem;
                margin-bottom: 0.34rem;
                display: block;
                transition: all .18s ease;
            }}
            [data-testid="stSidebar"] a[data-testid^="stPageLink"]:hover,
            [data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover,
            [data-testid="stSidebar"] a[kind="secondary"]:hover {{
                border-color: var(--ec-border);
                background: #101010;
                color: var(--ec-text) !important;
            }}

            .ec-status-card {{
                margin-top: 1.3rem;
                border-radius: 16px;
                border: 1px solid var(--ec-border);
                background: linear-gradient(180deg, #101010, #0D0D0D);
                padding: 0.95rem 0.9rem 1.15rem 0.9rem;
                position: relative;
                overflow: hidden;
            }}
            .ec-status-card::after {{
                content: "";
                position: absolute;
                left: 0;
                right: 0;
                bottom: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, var(--ec-red), transparent);
            }}
            .ec-status-head {{
                font-size: 0.78rem;
                letter-spacing: 0.08em;
                color: var(--ec-text-secondary);
                text-transform: uppercase;
                display: flex;
                align-items: center;
                gap: 0.45rem;
            }}
            .ec-dot {{ width: 9px; height: 9px; border-radius: 999px; display:inline-block; }}
            .ec-system-ok {{
                color: var(--ec-success);
                font-size: 0.95rem;
                margin-top: 0.7rem;
            }}
            .ec-status-illustration {{
                margin-top: 0.8rem;
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                background: radial-gradient(circle at 30% 20%, #1B1B1B 0%, #101010 70%);
                height: 72px;
                position: relative;
            }}
            .ec-status-illustration::before {{
                content: "";
                position: absolute;
                left: 10px;
                right: 20px;
                bottom: 16px;
                border-top: 1px dashed #3A3A3A;
                transform: skewX(-24deg);
            }}
            .ec-status-illustration::after {{
                content: "";
                position: absolute;
                width: 52px;
                height: 20px;
                left: 14px;
                top: 24px;
                border-radius: 4px;
                background: linear-gradient(180deg, #2A2A2A 0%, #151515 100%);
                border: 1px solid #3A3A3A;
            }}

            .ec-shell-main {{
                padding: 0.15rem 0.15rem 0.5rem 0.15rem;
            }}
            .ec-order-station {{
                color: var(--ec-red);
                letter-spacing: 0.07em;
                text-transform: uppercase;
                font-size: 1.0rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }}
            .ec-main-title {{
                font-size: clamp(2.5rem, 3.8vw, 3.35rem);
                font-weight: 800;
                line-height: 1.05;
                margin-bottom: 0.4rem;
                color: var(--ec-text);
            }}
            .ec-main-sub {{
                color: var(--ec-text-secondary);
                font-size: 1.38rem;
                margin-bottom: 1.7rem;
            }}

            .ec-section-row {{
                display:flex;
                align-items:center;
                gap:0.62rem;
                margin: 0.8rem 0 0.75rem 0;
            }}
            .ec-section-icon {{ color: #D9D9D9; font-size: 1.2rem; }}
            .ec-section-title {{
                font-size: 2.05rem;
                font-weight: 760;
                letter-spacing: -0.01em;
                position: relative;
                padding-bottom: 0.32rem;
            }}
            .ec-section-title::after {{
                content:"";
                position:absolute;
                left:0;
                bottom:-3px;
                width:34px;
                height:4px;
                border-radius: 99px;
                background: var(--ec-red);
            }}
            .ec-section-divider {{
                flex: 1;
                height: 1px;
                background: var(--ec-border);
                margin-left: 0.3rem;
            }}
            .ec-see-all {{
                color: var(--ec-red);
                font-size: 0.96rem;
                font-weight: 640;
                white-space: nowrap;
            }}

            .ec-menu-card {{
                border: 1px solid var(--ec-border);
                background: linear-gradient(180deg, #131313 0%, #101010 100%);
                border-radius: 16px;
                padding: 1rem;
                box-shadow: 0 10px 26px rgba(0,0,0,0.28);
                min-height: 268px;
                margin-bottom: 0.48rem;
                transition: border-color .2s ease;
                overflow: hidden;
                max-width: 100%;
                position: relative;
            }}
            .ec-menu-card:hover {{ border-color: #4A2426; }}
            .ec-menu-card.compact {{ min-height: 254px; padding: 0.88rem; }}
            .ec-menu-head {{ display:flex; gap:0.9rem; align-items:flex-start; min-width:0; padding-right: 0; }}
            .ec-thumb {{
                width: 82px;
                height: 82px;
                border-radius: 999px;
                background: radial-gradient(circle at 30% 30%, #4B4B4B 0%, #1C1C1C 72%);
                border: 1px solid #3B3B3B;
                display:flex;
                align-items:center;
                justify-content:center;
                font-size: 2rem;
                flex-shrink:0;
            }}
            .ec-menu-card.compact .ec-thumb {{ width: 74px; height: 74px; font-size: 1.72rem; }}
            .ec-menu-title-wrap {{ flex:1; min-width:0; max-width:100%; padding-right: 0.2rem; }}
            .ec-menu-name {{
                font-size: clamp(1.22rem, 2.1vw, 1.82rem);
                font-weight: 750;
                color: var(--ec-text);
                line-height: 1.08;
                overflow-wrap: normal;
                word-break: normal;
                hyphens: none;
                max-width: calc(100% - 5.8rem);
            }}
            .ec-menu-price {{
                color: var(--ec-red);
                font-size: clamp(1.55rem, 2.25vw, 2.02rem);
                font-weight: 780;
                margin-top: 0.18rem;
                white-space: nowrap;
            }}
            .ec-menu-desc {{
                color: var(--ec-text-secondary);
                font-size: 1.0rem;
                margin-top: 0.32rem;
                overflow-wrap: break-word;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
            .ec-status-pill {{
                border: 1px solid var(--ec-red);
                color: var(--ec-red);
                border-radius: 999px;
                font-size: 0.72rem;
                letter-spacing: 0.03em;
                font-weight: 700;
                padding: 0.22rem 0.58rem;
                text-transform: uppercase;
                align-self:flex-start;
                flex-shrink:0;
                position: absolute;
                top: 1rem;
                right: 1rem;
                background: #101010;
            }}
            .ec-status-pill.muted {{
                border-color: #525252;
                color: #989898;
            }}
            .ec-menu-meta {{
                margin-top: 0.82rem;
                border-top: 1px solid var(--ec-border);
                padding-top: 0.64rem;
                display:flex;
                gap:0.8rem;
                flex-wrap: wrap;
                color: var(--ec-text-secondary);
                font-size: 0.98rem;
            }}
            .ec-meta-sep {{ color: #505050; }}
            .ec-card-btn {{ margin-top: 0.6rem; }}

            .stButton > button {{
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                height: 44px;
                font-size: 1rem;
                font-weight: 650;
                color: var(--ec-text);
                background: var(--ec-card-elev);
            }}
            .stButton > button:hover {{
                border-color: #3C3C3C;
                color: var(--ec-text);
            }}
            .stButton > button[kind="primary"] {{
                background: linear-gradient(90deg, #B8151B 0%, var(--ec-red) 75%);
                border-color: transparent;
                color: #fff;
            }}
            .stButton > button[kind="primary"]:hover {{
                background: linear-gradient(90deg, #C9181F 0%, var(--ec-red-hover) 85%);
                color: #fff;
            }}

            .ec-right-topbar {{
                display:flex;
                align-items:center;
                justify-content:flex-end;
                gap:0.7rem;
                margin-bottom: 0.8rem;
            }}
            .ec-connected {{
                border:1px solid var(--ec-border);
                background:#0E0E0E;
                border-radius:12px;
                padding:0.44rem 0.72rem;
                display:flex;
                align-items:center;
                gap:0.5rem;
                color:#E2E2E2;
                font-size:0.9rem;
            }}
            .ec-avatar {{
                width:38px;
                height:38px;
                border-radius:999px;
                border:1px solid #3A3A3A;
                background: linear-gradient(180deg, #1D1D1D, #111111);
                display:flex;
                align-items:center;
                justify-content:center;
                font-weight:700;
                font-size:0.95rem;
            }}

            .ec-right-panel {{
                border:1px solid var(--ec-border);
                border-radius: 18px;
                background: linear-gradient(180deg, #121212 0%, #0D0D0D 100%);
                padding: 1rem;
                position: sticky;
                top: 18px;
            }}

            .ec-panel-title {{
                display:flex;
                align-items:center;
                justify-content:space-between;
                margin-bottom: 0.74rem;
            }}
            .ec-panel-title-left {{
                display:flex;
                align-items:center;
                gap:0.6rem;
                font-size:1.7rem;
                font-weight:740;
            }}
            .ec-clear-label {{
                color: var(--ec-red);
                font-weight: 620;
                font-size: 0.92rem;
            }}

            .ec-empty-cart {{
                border: 1px dashed #922125;
                border-radius: 14px;
                background: radial-gradient(circle at 60% 10%, #141414 0%, #101010 70%);
                padding: 1.8rem 1rem;
                text-align:center;
                margin-bottom: 1rem;
            }}
            .ec-empty-icon {{
                color: var(--ec-red);
                font-size: 2rem;
                margin-bottom: 0.3rem;
            }}
            .ec-empty-title {{ font-size: 1.12rem; font-weight: 700; color: var(--ec-text); }}
            .ec-empty-sub {{ margin-top: 0.3rem; color: var(--ec-text-secondary); }}

            .ec-cart-line {{
                border:1px solid var(--ec-border);
                border-radius:12px;
                background:#121212;
                padding:0.62rem 0.7rem;
                margin-bottom:0.55rem;
            }}
            .ec-cart-line-name {{ color:var(--ec-text); font-weight:650; font-size:0.97rem; }}
            .ec-cart-line-note {{ color:var(--ec-text-secondary); font-size:0.82rem; margin-top:0.12rem; }}

            .ec-metrics-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:0.62rem; margin-top:0.35rem; margin-bottom: 1rem; }}
            .ec-metric-tile {{
                border:1px solid var(--ec-border);
                border-radius:12px;
                background:var(--ec-card-elev);
                padding:0.72rem;
            }}
            .ec-metric-label {{
                color:var(--ec-text-secondary);
                font-size:0.74rem;
                letter-spacing:0.08em;
                text-transform:uppercase;
            }}
            .ec-metric-value {{
                margin-top:0.3rem;
                font-size:1.2rem;
                font-weight:760;
                color:var(--ec-text);
            }}

            .ec-module {{
                border-top: 1px solid var(--ec-border);
                padding-top: 0.85rem;
                margin-top: 0.75rem;
            }}
            .ec-module-title {{
                display:flex;
                align-items:center;
                gap:0.54rem;
                font-size:1.15rem;
                font-weight:700;
                color:var(--ec-text);
            }}
            .ec-module-sub {{ margin-top:0.26rem; color:var(--ec-text-secondary); font-size:0.94rem; }}

            .ec-voice-box {{
                margin-top:0.62rem;
                border:1px solid var(--ec-border);
                border-radius:14px;
                background: radial-gradient(circle at 50% 10%, #171717 0%, #121212 72%);
                padding: 0.9rem;
                text-align:center;
            }}
            .ec-wave-wrap {{ display:flex; align-items:center; justify-content:center; gap:0.55rem; margin-bottom:0.4rem; }}
            .ec-wave {{
                width: 110px;
                height: 34px;
                background: repeating-linear-gradient(
                    90deg,
                    transparent 0,
                    transparent 5px,
                    rgba(215,25,32,0.9) 5px,
                    rgba(215,25,32,0.9) 7px
                );
                clip-path: polygon(0 50%, 4% 40%, 8% 65%, 12% 28%, 16% 73%, 20% 34%, 24% 58%, 28% 38%, 32% 70%, 36% 35%, 40% 62%, 44% 45%, 48% 72%, 52% 30%, 56% 66%, 60% 45%, 64% 70%, 68% 38%, 72% 63%, 76% 30%, 80% 68%, 84% 43%, 88% 62%, 92% 40%, 96% 57%, 100% 50%);
                opacity: 0.86;
            }}
            .ec-mic-btn {{
                width: 72px;
                height: 72px;
                border-radius: 999px;
                border: 2px solid rgba(255,255,255,0.12);
                background: radial-gradient(circle at 35% 25%, var(--ec-red-hover) 0%, var(--ec-red) 60%, #A11217 100%);
                display:flex;
                align-items:center;
                justify-content:center;
                box-shadow: 0 0 0 8px rgba(215,25,32,0.15), 0 8px 24px rgba(0,0,0,0.35);
                color:#fff;
                font-size:1.55rem;
                font-weight:800;
            }}
            .ec-voice-time {{ color: var(--ec-text-secondary); font-size: 0.95rem; margin-top: 0.12rem; }}

            .stTextInput > div > div > input {{
                background: #111111;
                color: var(--ec-text);
                border: 1px solid var(--ec-border);
                border-radius: 10px;
                height: 44px;
            }}
            .stTextInput label {{
                color: var(--ec-text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-size: 0.73rem;
            }}
            [data-testid="stAudioInput"] {{
                margin-top: 0.55rem;
            }}
            [data-testid="stAudioInput"] button {{
                border-radius: 10px;
                border-color: var(--ec-border);
                background: #111;
                color: var(--ec-text);
            }}

            .ec-footer-spacer {{ height: 0.4rem; }}

            @media (max-width: 1300px) {{
                .ec-menu-head {{ gap: 0.7rem; }}
                .ec-thumb {{ width: 68px; height: 68px; font-size: 1.72rem; }}
                .ec-menu-price {{ font-size: 1.74rem; }}
                .ec-status-pill {{ display: none; }}
                .ec-menu-name {{ max-width: 100%; }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_logo() -> None:
    st.sidebar.markdown(
        """
        <div class="ec-brand">
            <svg width="132" height="70" viewBox="0 0 132 70" xmlns="http://www.w3.org/2000/svg" style="display:block;margin-bottom:0.55rem;">
                <path d="M18 41 C36 20, 50 20, 70 35 C82 44, 95 46, 111 41" stroke="#ECECEC" stroke-width="2.4" fill="none" stroke-linecap="round"/>
                <path d="M24 51 C42 36, 56 36, 74 49" stroke="#9A9A9A" stroke-width="2" fill="none" stroke-linecap="round"/>
                <path d="M44 29 C53 12, 76 8, 92 21" stroke="#D71920" stroke-width="3" fill="none" stroke-linecap="round"/>
                <path d="M91 20 C91 12, 84 6, 75 6 C66 6, 59 12, 59 20" fill="#D71920" stroke="#D71920"/>
                <circle cx="75" cy="20" r="1.6" fill="#0D0D0D"/>
                <circle cx="81" cy="18" r="1.3" fill="#0D0D0D"/>
                <circle cx="69" cy="18" r="1.3" fill="#0D0D0D"/>
            </svg>
            <div class="ec-brand-title">EL CAMINO</div>
            <div class="ec-brand-sub">AI FOOD TRUCK OS</div>
            <div class="ec-brand-tagline">Run the truck. Serve with precision.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav_item(label: str, icon: str, active: bool = False, page: str | None = None) -> None:
    if active:
        st.sidebar.markdown(
            f"<div class='ec-nav-item active'><span class='ec-nav-icon'>{escape(icon)}</span><span>{escape(label)}</span></div>",
            unsafe_allow_html=True,
        )
        return

    if hasattr(st, "page_link") and page:
        st.sidebar.page_link(page, label=f"{icon}  {label}")
    else:
        st.sidebar.markdown(
            f"<div class='ec-nav-item'><span class='ec-nav-icon'>{escape(icon)}</span><span>{escape(label)}</span></div>",
            unsafe_allow_html=True,
        )


def render_status_card() -> None:
    st.sidebar.markdown(
        """
        <div class="ec-status-card">
            <div class="ec-status-head"><span class="ec-dot" style="background:#D71920;"></span> SYSTEM STATUS</div>
            <div class="ec-system-ok">All systems operational</div>
            <div class="ec-status-illustration"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    render_brand_logo()
    for label, icon, page, active in NAV_ITEMS:
        render_nav_item(label, icon, active=active, page=page)
    render_status_card()


def render_status_pill(label: str, variant: str) -> str:
    cls = "ec-status-pill"
    if variant == "muted":
        cls += " muted"
    return f"<span class='{cls}'>{escape(label)}</span>"


def render_primary_button(label: str) -> str:
    return f"＋  {label}"


def _minutes(value: object, fallback: float) -> float:
    if value is None or value == "":
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _minute_label(value: float, zero_label: str) -> str:
    return zero_label if value <= 0 else f"{value:.1f}m"


def _item_emoji(item: dict) -> str:
    category = str(item.get("category") or "").lower()
    name = str(item.get("name") or "").lower()
    if "burrito" in name or category == "burritos":
        return "🌯"
    if category == "drinks" or "coke" in name or "lemonade" in name or "horchata" in name:
        return "🥤"
    if "taco" in name or category == "tacos":
        return "🌮"
    if category == "sides" or "nachos" in name or "chips" in name:
        return "🥑"
    return "🍽️"


def render_menu_card(item: dict, compact: bool = False) -> None:
    available = bool(item.get("available"))
    pill = render_status_pill("HEALTHY", "healthy") if available else render_status_pill("UNAVAILABLE", "muted")
    card_class = "ec-menu-card compact" if compact else "ec-menu-card"

    desc = escape(item.get("description") or "")
    prep = _minutes(item.get("prep_time_minutes"), 1)
    cook = _minutes(item.get("cook_time_minutes"), 5)
    if has_placeholder_timing(item):
        prep, cook = estimate_menu_timing(item)

    st.markdown(
        f"""
        <div class="{card_class}">
            <div class="ec-menu-head">
                <div class="ec-thumb">{_item_emoji(item)}</div>
                <div class="ec-menu-title-wrap">
                    {pill}
                    <div class="ec-menu-name">{escape(str(item['name']))}</div>
                    <div class="ec-menu-price">${float(item['price']):.2f}</div>
                    <div class="ec-menu-desc">{desc}</div>
                </div>
            </div>
            <div class="ec-menu-meta">
                <span>◷ Prep {_minute_label(prep, "Ready")}</span>
                <span class="ec-meta-sep">|</span>
                <span>◶ {_minute_label(cook, "No cook")}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        render_primary_button("Add to Order"),
        key=f"add_menu_{item['id']}",
        type="primary",
        use_container_width=True,
        disabled=not available,
    ):
        add_to_cart(item)
        st.rerun()


def render_menu_section(
    title: str,
    icon: str,
    items: list[dict],
    columns: int,
    compact: bool = False,
    preview_only: bool = False,
) -> None:
    st.markdown(
        f"""
        <div class="ec-section-row">
            <div class="ec-section-icon">{escape(icon)}</div>
            <div class="ec-section-title">{escape(title)}</div>
            <div class="ec-section-divider"></div>
            <div class="ec-see-all">See all  ›</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if preview_only:
        st.markdown("<div class='ec-footer-spacer'></div>", unsafe_allow_html=True)
        with st.expander("Show full Tacos & Sides menu"):
            cols = st.columns(columns)
            for idx, item in enumerate(items):
                with cols[idx % columns]:
                    render_menu_card(item, compact=compact)
        return

    cols = st.columns(columns)
    for idx, item in enumerate(items):
        with cols[idx % columns]:
            render_menu_card(item, compact=compact)


def render_metric_tile(label: str, value: str, icon: str | None = None) -> str:
    icon_html = f"<span style='float:right;color:{EL_CAMINO_THEME['text_secondary']};'>{escape(icon)}</span>" if icon else ""
    return (
        "<div class='ec-metric-tile'>"
        f"<div class='ec-metric-label'>{escape(label)} {icon_html}</div>"
        f"<div class='ec-metric-value'>{escape(value)}</div>"
        "</div>"
    )


def render_cart_panel(cart: list[dict], menu_lookup: dict[int, dict]) -> None:
    st.markdown(
        """
        <div class="ec-panel-title">
            <div class="ec-panel-title-left">🛒 <span>Cart</span></div>
            <div class="ec-clear-label">Clear Cart</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    clear_col, _ = st.columns([1, 1.7])
    with clear_col:
        if st.button("🗑 Clear", key="clear_cart", use_container_width=True, disabled=not bool(cart)):
            st.session_state.cart = []
            st.rerun()

    if not cart:
        st.markdown(
            """
            <div class="ec-empty-cart">
                <div class="ec-empty-icon">🌮</div>
                <div class="ec-empty-title">Your cart is empty</div>
                <div class="ec-empty-sub">Add items from the menu to get started.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for idx, line in enumerate(cart):
            with st.container():
                st.markdown("<div class='ec-cart-line'>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([4.2, 1.3, 1])
                with c1:
                    st.markdown(f"<div class='ec-cart-line-name'>{line['quantity']}x {escape(line['name'])}</div>", unsafe_allow_html=True)
                    if line.get("notes"):
                        st.markdown(f"<div class='ec-cart-line-note'>{escape(str(line['notes']))}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='ec-cart-line-name'>${line['price'] * line['quantity']:.2f}</div>", unsafe_allow_html=True)
                with c3:
                    if st.button("✕", key=f"remove_line_{idx}", use_container_width=True):
                        remove_line(idx)
                        st.rerun()

                q1, q2 = st.columns(2)
                with q1:
                    if st.button("−", key=f"dec_qty_{idx}", use_container_width=True):
                        line["quantity"] = max(0, line["quantity"] - 1)
                        if line["quantity"] == 0:
                            remove_line(idx)
                        st.rerun()
                with q2:
                    if st.button("+", key=f"inc_qty_{idx}", use_container_width=True):
                        line["quantity"] += 1
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    wait = wait_time_preview(menu_lookup, cart)
    st.markdown(
        "<div class='ec-metrics-grid'>"
        + render_metric_tile("TOTAL", f"${cart_total():.2f}")
        + render_metric_tile("EST WAIT", f"{wait:.1f}m" if wait else "--", icon="◷")
        + "</div>",
        unsafe_allow_html=True,
    )


def render_voice_ordering_panel() -> None:
    st.markdown(
        """
        <div class="ec-module">
            <div class="ec-module-title">◉ Voice Ordering</div>
            <div class="ec-module-sub">Use natural language to add items to your cart.</div>
            <div class="ec-voice-box">
                <div class="ec-wave-wrap">
                    <div class="ec-wave"></div>
                    <div class="ec-mic-btn">🎙</div>
                    <div class="ec-wave"></div>
                </div>
                <div class="ec-voice-time">00:00</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    audio = st.audio_input("Record voice order", label_visibility="collapsed")
    if audio is None:
        return

    with st.spinner("Transcribing voice order..."):
        try:
            transcript = agents.transcribe_audio(audio.read(), filename="input.wav")
        except Exception as exc:  # pragma: no cover - network/runtime key dependent
            transcript = None
            st.error(f"Transcription failed: {exc}")

    if not transcript:
        return

    st.info(f"You said: {transcript}")
    with st.spinner("Updating cart..."):
        parsed = agents.parse_voice_order(transcript, st.session_state.cart)
        st.session_state.cart = agents.apply_actions_to_cart(
            st.session_state.cart,
            parsed.get("actions", []),
        )
        st.session_state.voice_log.append(
            {
                "transcript": transcript,
                "reply": parsed.get("reply", ""),
                "actions": parsed.get("actions", []),
            }
        )

    if st.session_state.voice_log and st.session_state.voice_log[-1].get("reply"):
        st.success(st.session_state.voice_log[-1]["reply"])
    st.rerun()


def render_checkout_panel(menu_lookup: dict[int, dict]) -> None:
    st.markdown(
        """
        <div class="ec-module">
            <div class="ec-module-title">◌ Checkout</div>
            <div class="ec-module-sub">Name for the order</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    customer_name = st.text_input("Name for the order", value="", placeholder="e.g. John Doe")
    can_checkout = bool(st.session_state.cart) and bool(customer_name.strip())

    if st.button("Place Order  ›", key="place_order", type="primary", use_container_width=True, disabled=not can_checkout):
        payload = [
            {
                "menu_id": line["menu_id"],
                "quantity": line["quantity"],
                "notes": line.get("notes"),
            }
            for line in st.session_state.cart
        ]
        with st.spinner("Placing order..."):
            result = orders_mod.create_order(payload, customer_name=customer_name.strip(), source="kiosk")

        if result.get("ok"):
            st.success(
                f"Order {result['order_number']} placed · Total ${result['total']:.2f} · "
                f"Est wait {result.get('estimated_wait_minutes') or '--'}m"
            )
            if hasattr(st, "page_link"):
                st.page_link("pages/9_🔎_Order_Status.py", label="Check your order status")
            st.session_state.cart = []
            st.rerun()
        else:
            st.error(f"Order failed: {result.get('error', 'unknown_error')}")
            if result.get("missing_ingredients"):
                st.caption("Missing: " + ", ".join(result["missing_ingredients"]))


def render_top_status_bar() -> None:
    st.markdown(
        """
        <div class="ec-right-topbar">
            <div class="ec-connected"><span class="ec-dot" style="background:#22C55E;"></span> CONNECTED</div>
            <div class="ec-connected">Deploy</div>
            <div class="ec-avatar">EC</div>
            <div style="color:#A8A8A8;">⌄</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Business logic helpers (preserve existing deterministic behavior)
# -----------------------------------------------------------------------------

def cart_total() -> float:
    return sum(c["price"] * c["quantity"] for c in st.session_state.cart)


def add_to_cart(menu_item: dict, qty: int = 1) -> None:
    for c in st.session_state.cart:
        if c["menu_id"] == menu_item["id"] and c.get("notes") in {None, ""}:
            c["quantity"] += qty
            return
    st.session_state.cart.append(
        {
            "menu_id": menu_item["id"],
            "name": menu_item["name"],
            "price": menu_item["price"],
            "quantity": qty,
            "notes": None,
        }
    )


def remove_line(idx: int) -> None:
    if 0 <= idx < len(st.session_state.cart):
        st.session_state.cart.pop(idx)


def wait_time_preview(menu_lookup: dict[int, dict], cart: list[dict]) -> float:
    if not cart:
        return 0.0

    durations = []
    for line in cart:
        menu = menu_lookup.get(line["menu_id"])
        if not menu:
            continue
        if has_placeholder_timing(menu):
            prep, cook = estimate_menu_timing(menu)
        else:
            prep = _minutes(menu.get("prep_time_minutes"), 1)
            cook = _minutes(menu.get("cook_time_minutes"), 5)
        per = prep + cook
        qty = max(int(line.get("quantity") or 1), 1)
        durations.append(per + max(0, qty - 1) * (per * 0.6))

    if not durations:
        return 0.0

    cfg = config_mod.get_business_config()
    buffer = float(cfg.get("defaultPrepBufferMinutes", 0) or 0)
    return round(max(durations) + buffer, 1)


# -----------------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------------
apply_el_camino_theme()
render_sidebar()

menu = orders_mod.get_menu(only_available=False)
menu_lookup = {m["id"]: m for m in menu}
unavailable_rows = inventory_mod.get_unavailable_menu_items()

by_category: dict[str, list[dict]] = defaultdict(list)
for item in menu:
    by_category[str(item.get("category") or "other").lower()].append(item)

burritos_items = by_category.get("burritos", [])
drinks_items = by_category.get("drinks", [])
tacos_sides_items = by_category.get("tacos", []) + by_category.get("sides", [])

main_col, right_col = st.columns([2.2, 1], gap="large")

with main_col:
    st.markdown("<div class='ec-shell-main'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ec-order-station">ORDER STATION</div>
        <div class="ec-main-title">Customer Order</div>
        <div class="ec-main-sub">Tap menu items or use voice. Deterministic totals and timing.</div>
        """,
        unsafe_allow_html=True,
    )

    if unavailable_rows:
        with st.expander("Availability warnings"):
            for row in unavailable_rows:
                blockers = row.get("blocking_ingredients") or []
                blocker_text = ", ".join(b["ingredient"] for b in blockers) if blockers and isinstance(blockers[0], dict) else ", ".join(blockers)
                st.warning(f"{row['menu_name']} unavailable: {blocker_text or 'ingredient constraints'}")

    if burritos_items:
        meta = CATEGORY_UI["burritos"]
        render_menu_section(meta["title"], meta["icon"], burritos_items, meta["columns"], compact=meta["compact"])

    if drinks_items:
        meta = CATEGORY_UI["drinks"]
        render_menu_section(meta["title"], meta["icon"], drinks_items, meta["columns"], compact=meta["compact"])

    if tacos_sides_items:
        meta = CATEGORY_UI["tacos_sides"]
        render_menu_section(
            meta["title"],
            meta["icon"],
            tacos_sides_items,
            meta["columns"],
            compact=meta["compact"],
            preview_only=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    render_top_status_bar()
    st.markdown("<div class='ec-right-panel'>", unsafe_allow_html=True)
    render_cart_panel(st.session_state.cart, menu_lookup)
    render_voice_ordering_panel()
    render_checkout_panel(menu_lookup)
    st.markdown("</div>", unsafe_allow_html=True)
