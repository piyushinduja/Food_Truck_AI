"""Entry point for El Camino.

Default behavior: open the premium Order command-center page.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from backend.bootstrap import ensure_app_ready
from backend.db import reset_db
from backend.seed import seed


st.set_page_config(
    page_title="EL CAMINO",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_app_ready()

# Streamlit >= 1.27 supports switch_page. In this project we target current
# Streamlit, so default app load should immediately show the Order UI.
if hasattr(st, "switch_page"):
    st.switch_page("pages/1_🍽️_Order.py")

# Fallback view only if switch_page is unavailable.
st.markdown(
    """
    <style>
      .stApp { background: #070707; color: #fff; }
      .block-container { padding-top: 4rem; max-width: 900px; }
      .hero { font-size: 3rem; font-weight: 800; margin-bottom: 0.5rem; }
      .sub { color: #A8A8A8; margin-bottom: 2rem; }
    </style>
    <div class='hero'>EL CAMINO</div>
    <div class='sub'>AI FOOD TRUCK OS · Run the truck. Serve with precision.</div>
    """,
    unsafe_allow_html=True,
)

if hasattr(st, "page_link"):
    st.page_link("pages/1_🍽️_Order.py", label="Open Order Station", icon="🍽️")

with st.sidebar:
    if st.button("Reset Database", use_container_width=True):
        reset_db()
        seed()
        st.success("Reset complete.")
        st.rerun()
