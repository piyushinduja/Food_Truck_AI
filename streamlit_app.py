"""El Camino entry point with Customer/Owner split."""
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
from backend.ui_components import (
    CUSTOMER_PAGE_ORDER,
    OWNER_PAGE_DASHBOARD,
    VIEW_CUSTOMER,
    VIEW_OWNER,
    apply_el_camino_theme,
    set_view_mode,
)


st.set_page_config(
    page_title="El Camino",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ensure_app_ready()
apply_el_camino_theme()

st.markdown("## EL CAMINO")
st.caption("One platform. Two connected experiences.")

left, right = st.columns(2, gap="large")

with left:
    st.markdown("### Customer View")
    st.markdown(
        """
        <div class='ec-panel'>
          <h4 style='margin-top:0;'>Order Food</h4>
          <p style='margin-bottom:0;color:#B8B8B8;'>
            Fast menu ordering and real-time order tracking.
            Optimized for kiosk/tablet flow.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Customer View", type="primary", width='stretch'):
        set_view_mode(VIEW_CUSTOMER)
        if hasattr(st, "switch_page"):
            st.switch_page(CUSTOMER_PAGE_ORDER)

with right:
    st.markdown("### Owner View")
    st.markdown(
        """
        <div class='ec-panel'>
          <h4 style='margin-top:0;'>Run the Truck</h4>
          <p style='margin-bottom:0;color:#B8B8B8;'>
            Command center for kitchen, inventory, purchasing,
            analytics, assistant, and autopilot.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Owner View", type="primary", width='stretch'):
        set_view_mode(VIEW_OWNER)
        if hasattr(st, "switch_page"):
            st.switch_page(OWNER_PAGE_DASHBOARD)

st.divider()
st.caption("Customer and Owner views share the same live SQLite state.")

with st.expander("Admin", expanded=False):
    if st.button("Reset Database", width='stretch'):
        reset_db()
        seed()
        st.success("Reset complete.")
        st.rerun()
