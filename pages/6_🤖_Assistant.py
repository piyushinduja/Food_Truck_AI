"""Owner assistant chat page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import streamlit as st

from backend import agents
from backend.bootstrap import ensure_app_ready
from backend.ui_components import VIEW_OWNER, enforce_view_mode, render_app_shell, render_section_header


st.set_page_config(page_title="Owner Assistant — El Camino", page_icon="🤖", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Assistant", "Tool-grounded owner assistant")

SUGGESTIONS = [
    "What needs attention right now?",
    "Show inventory and expiry risks.",
    "Give me today's revenue, COGS, and estimated profit.",
    "List purchase orders waiting for approval.",
]

if "owner_messages" not in st.session_state:
    st.session_state.owner_messages = []

for message in st.session_state.owner_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not st.session_state.owner_messages:
    suggestion_cols = st.columns(len(SUGGESTIONS))
    for col, text in zip(suggestion_cols, SUGGESTIONS):
        with col:
            if st.button(text, width='stretch'):
                st.session_state.pending_prompt = text
                st.rerun()

prompt = st.chat_input("Ask about kitchen, inventory, purchasing, and money...")
prompt = prompt or st.session_state.pop("pending_prompt", None)

if prompt:
    st.session_state.owner_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                api_messages = [{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.owner_messages]
                result = agents.owner_chat(api_messages)
            except Exception as exc:
                result = {"reply": f"Assistant error: {exc}", "tool_calls": []}
        st.markdown(result["reply"])

    st.session_state.owner_messages.append({"role": "assistant", "content": result["reply"]})

with st.sidebar:
    if st.button("Clear Chat", width='stretch'):
        st.session_state.owner_messages = []
        st.rerun()
