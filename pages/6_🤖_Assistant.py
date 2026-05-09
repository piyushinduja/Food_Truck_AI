"""Owner Assistant — natural-language chat with tool access.

The agent can query sales, inventory, and revenue, and place restock
orders. Uses Groq for the chat completion + tool calls.
"""
import _path_setup  # noqa: F401
import streamlit as st

from backend import agents


st.set_page_config(page_title="Assistant — El Camino", page_icon="🤖", layout="wide")
st.title("🤖 Owner Assistant")
st.caption("Ask about sales, inventory, revenue. The assistant can place restocks too.")


SUGGESTIONS = [
    "What's my best-seller this week?",
    "How did revenue look over the last 14 days?",
    "What ingredients are running low?",
    "Suggest restocks and tell me the total cost.",
    "How's today going?",
]


if "owner_messages" not in st.session_state:
    st.session_state.owner_messages = []


# Render history
for msg in st.session_state.owner_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                with st.expander(f"🔧 Tools called ({len(msg['tool_calls'])})"):
                    for tc in msg["tool_calls"]:
                        st.markdown(f"**{tc['name']}**({tc['args']})")
                        st.json(tc["result"], expanded=False)


# Suggestion chips (only show when no chat yet)
if not st.session_state.owner_messages:
    st.markdown("**Try asking:**")
    cols = st.columns(len(SUGGESTIONS))
    for col, s in zip(cols, SUGGESTIONS):
        with col:
            if st.button(s, use_container_width=True, key=f"sug_{s}"):
                st.session_state.pending_input = s
                st.rerun()


# Input
prompt = st.chat_input("Ask about your business...")
pending = st.session_state.pop("pending_input", None)
prompt = prompt or pending

if prompt:
    st.session_state.owner_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Send only role/content for the LLM call (strip our tool_calls metadata)
                api_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.owner_messages
                ]
                result = agents.owner_chat(api_messages)
            except Exception as e:
                result = {"reply": f"Error: {e}", "tool_calls": []}

        st.markdown(result["reply"])
        if result["tool_calls"]:
            with st.expander(f"🔧 Tools called ({len(result['tool_calls'])})"):
                for tc in result["tool_calls"]:
                    st.markdown(f"**{tc['name']}**({tc['args']})")
                    st.json(tc["result"], expanded=False)

    st.session_state.owner_messages.append({
        "role": "assistant",
        "content": result["reply"],
        "tool_calls": result["tool_calls"],
    })


with st.sidebar:
    if st.button("Clear chat", use_container_width=True):
        st.session_state.owner_messages = []
        st.rerun()
