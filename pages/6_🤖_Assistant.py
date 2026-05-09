"""Owner assistant chat page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import streamlit as st

from backend import agents
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, section_header


st.set_page_config(page_title="Owner Assistant — El Camino", page_icon="🤖", layout="wide")
ensure_app_ready()
apply_global_theme()

section_header("Owner Assistant", "Tool-grounded operations chat. No fabricated numbers.")

SUGGESTIONS = [
    "What needs attention right now?",
    "Show me inventory alerts and expiry risks.",
    "Give me today's revenue, COGS, and estimated profit.",
    "List purchase orders waiting for approval.",
    "Create purchase orders for the urgent restocks.",
]

if "owner_messages" not in st.session_state:
    st.session_state.owner_messages = []

for msg in st.session_state.owner_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            with st.expander(f"Tool calls ({len(msg['tool_calls'])})"):
                for tc in msg["tool_calls"]:
                    st.markdown(f"**{tc['name']}** {tc['args']}")
                    st.json(tc["result"], expanded=False)

if not st.session_state.owner_messages:
    cols = st.columns(len(SUGGESTIONS))
    for col, text in zip(cols, SUGGESTIONS):
        with col:
            if st.button(text, use_container_width=True):
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
                api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.owner_messages]
                result = agents.owner_chat(api_messages)
            except Exception as exc:  # pragma: no cover - runtime/api dependent
                result = {"reply": f"Error: {exc}", "tool_calls": []}

        st.markdown(result["reply"])
        if result["tool_calls"]:
            with st.expander(f"Tool calls ({len(result['tool_calls'])})"):
                for tc in result["tool_calls"]:
                    st.markdown(f"**{tc['name']}** {tc['args']}")
                    st.json(tc["result"], expanded=False)

    st.session_state.owner_messages.append(
        {
            "role": "assistant",
            "content": result["reply"],
            "tool_calls": result["tool_calls"],
        }
    )

with st.sidebar:
    if st.button("Clear chat", use_container_width=True):
        st.session_state.owner_messages = []
        st.rerun()
