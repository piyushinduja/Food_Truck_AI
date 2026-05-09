"""Food Truck Operations — Streamlit entry point.

Run with: streamlit run streamlit_app.py

The sidebar exposes a demo reset button and shows quick stats.
The actual pages live under pages/ and are auto-discovered by Streamlit.
"""
import sys
from pathlib import Path

# Make sure project root is on sys.path so `from backend import ...` works
# regardless of which directory `streamlit run` was invoked from.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from backend.db import reset_db, init_db
from backend.seed import seed
from backend import analytics, orders as orders_mod


st.set_page_config(
    page_title="El Camino — Operations",
    page_icon="🌮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Initialize DB on first run
DB_PATH = _PROJECT_ROOT / "data" / "foodtruck.db"
if not DB_PATH.exists():
    init_db()
    seed()


# Custom styling — warm palette, distinctive but Streamlit-compatible
st.markdown("""
<style>
    .main > div { padding-top: 1.5rem; }
    h1, h2, h3 { font-family: 'Georgia', serif; letter-spacing: -0.02em; }
    .hero-title {
        font-size: 3.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #d4471a 0%, #f4a261 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .hero-sub {
        color: #888;
        font-size: 1.1rem;
        font-style: italic;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: #fafafa;
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 4px solid #d4471a;
    }
    .stat-label { color: #888; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 2rem; font-weight: 700; color: #222; margin-top: 0.3rem; }
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="hero-title">🌮 El Camino</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Run-your-business AI for food trucks</div>', unsafe_allow_html=True)


# Quick stats row
summary = analytics.today_summary()
active_orders = orders_mod.list_active_orders()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Today\'s Revenue</div><div class="stat-value">${summary["revenue"]:.2f}</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Orders Today</div><div class="stat-value">{summary["num_orders"]}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Avg Ticket</div><div class="stat-value">${summary["avg_ticket"]:.2f}</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="stat-card"><div class="stat-label">Active Orders</div><div class="stat-value">{len(active_orders)}</div></div>', unsafe_allow_html=True)


st.markdown("### ")
st.markdown("""
Welcome to the operations console. Use the sidebar to navigate:

- **🍽️ Order** — customer-facing menu with click-to-add and voice ordering
- **👨‍🍳 Kitchen** — active orders queue with timers and status flow
- **📦 Inventory** — stock levels, low-stock alerts, restock from supplier
- **📊 Sales** — best-sellers and category breakdown
- **💰 Revenue** — daily revenue trends
- **🤖 Owner Assistant** — ask questions about your business in plain language
""")


# Sidebar demo controls
with st.sidebar:
    st.markdown("### Demo Controls")
    if st.button("🔄 Reset Database", use_container_width=True):
        reset_db()
        seed()
        st.success("Reset and re-seeded.")
        st.rerun()

    st.markdown("---")
    st.markdown("### Active Now")
    if active_orders:
        for o in active_orders[:5]:
            st.markdown(f"**#{o['id']}** — {o['status']} · ${o['total']:.2f}")
    else:
        st.markdown("*No active orders*")

    st.markdown("---")
    st.caption("Built for Anthropic hackathon.")
    st.caption("LLM: Groq · DB: SQLite · UI: Streamlit")
