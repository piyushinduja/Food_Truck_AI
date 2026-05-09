"""Customer order page — click items, edit cart by voice."""
import _path_setup  # noqa: F401  -- must be first, makes 'backend' importable
import streamlit as st
from collections import defaultdict

from backend import orders as orders_mod, agents


st.set_page_config(page_title="Order — El Camino", page_icon="🍽️", layout="wide")
st.title("🍽️ Order")
st.caption("Tap items to add. Use the mic to make changes by voice.")


# ---- Cart in session state ----
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of {menu_id, name, price, quantity, notes}
if "voice_log" not in st.session_state:
    st.session_state.voice_log = []  # list of {transcript, reply}


def cart_total() -> float:
    return sum(c["price"] * c["quantity"] for c in st.session_state.cart)


def add_to_cart(menu_item: dict, qty: int = 1):
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


def remove_line(idx: int):
    if 0 <= idx < len(st.session_state.cart):
        st.session_state.cart.pop(idx)


# ---- Layout: menu on the left, cart on the right ----
left, right = st.columns([2, 1])

with left:
    menu = orders_mod.get_menu()
    by_category = defaultdict(list)
    for m in menu:
        by_category[m["category"]].append(m)

    category_emoji = {"tacos": "🌮", "burritos": "🌯", "sides": "🥑", "drinks": "🥤"}
    category_order = ["tacos", "burritos", "sides", "drinks"]

    for cat in category_order:
        items = by_category.get(cat, [])
        if not items:
            continue
        st.subheader(f"{category_emoji.get(cat, '·')} {cat.title()}")
        cols = st.columns(2)
        for i, item in enumerate(items):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{item['name']}** &nbsp; · &nbsp; ${item['price']:.2f}")
                    st.caption(item["description"])
                    if st.button("Add", key=f"add_{item['id']}", width='stretch'):
                        add_to_cart(item)
                        st.rerun()


with right:
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Cart is empty.")
    else:
        for idx, line in enumerate(st.session_state.cart):
            with st.container(border=True):
                top = st.columns([3, 1])
                with top[0]:
                    st.markdown(f"**{line['quantity']}× {line['name']}**")
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

        st.markdown("---")
        st.markdown(f"### Total: ${cart_total():.2f}")

    # ---- Voice editing ----
    st.markdown("---")
    st.subheader("🎙️ Edit by Voice")
    st.caption("Try: *'two carne tacos and a coke'* or *'no cilantro on the first taco'*")

    audio = st.audio_input("Record")
    if audio is not None:
        with st.spinner("Listening..."):
            try:
                audio_bytes = audio.read()
                transcript = agents.transcribe_audio(audio_bytes, filename="input.wav")
            except Exception as e:
                st.error(f"Transcription failed: {e}")
                transcript = None

        if transcript:
            st.markdown(f"**You said:** _{transcript}_")
            with st.spinner("Updating cart..."):
                try:
                    parsed = agents.parse_voice_order(transcript, st.session_state.cart)
                    st.session_state.cart = agents.apply_actions_to_cart(
                        st.session_state.cart, parsed.get("actions", [])
                    )
                    st.session_state.voice_log.append({
                        "transcript": transcript,
                        "reply": parsed.get("reply", ""),
                        "actions": parsed.get("actions", []),
                    })
                    if parsed.get("reply"):
                        st.success(parsed["reply"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't process that: {e}")

    if st.session_state.voice_log:
        with st.expander("Voice history"):
            for entry in st.session_state.voice_log[-5:]:
                st.markdown(f"🗣️ _{entry['transcript']}_")
                st.markdown(f"🤖 {entry['reply']}")
                st.markdown("---")

    # ---- Checkout ----
    st.markdown("---")
    name = st.text_input("Your name (for the order)", value="", placeholder="e.g. Maria")
    phone = st.text_input("Phone for SMS updates (optional)", value="", placeholder="e.g. +15551234567")
    can_checkout = bool(st.session_state.cart) and bool(name.strip())

    if st.button("Place Order & Pay", type="primary", width='stretch', disabled=not can_checkout):
        cart_payload = [
            {"menu_id": c["menu_id"], "quantity": c["quantity"], "notes": c.get("notes")}
            for c in st.session_state.cart
        ]
        with st.spinner("Charging card..."):
            result = orders_mod.create_order(
                cart_payload,
                customer_name=name.strip(),
                phone=phone.strip() or None,
            )

        if result["ok"]:
            st.success(f"Order #{result['order_id']} placed! Total ${result['total']:.2f}")
            st.balloons()
            st.session_state.cart = []
            st.session_state.voice_log = []
        else:
            err = result.get("error", "unknown")
            st.error(f"Order failed: {err}")
            if "missing_ingredients" in result:
                st.caption(f"Missing: {', '.join(result['missing_ingredients'])}")
