"""Customer kiosk order page."""
from __future__ import annotations

import _path_setup  # noqa: F401
from collections import defaultdict

import streamlit as st

from backend import agents, orders as orders_mod
from backend import config as config_mod
from backend import inventory as inventory_mod
from backend.bootstrap import ensure_app_ready
from backend.theme import apply_global_theme, command_card, metric_card, section_header


st.set_page_config(page_title="Customer Order — El Camino", page_icon="🍽️", layout="wide")
ensure_app_ready()
apply_global_theme()

section_header("Customer Order", "Tap menu items or use voice. Deterministic totals and timing.")

if "cart" not in st.session_state:
    st.session_state.cart = []
if "voice_log" not in st.session_state:
    st.session_state.voice_log = []


def cart_total() -> float:
    return sum(c["price"] * c["quantity"] for c in st.session_state.cart)


def add_to_cart(menu_item: dict, qty: int = 1) -> None:
    for c in st.session_state.cart:
        if c["menu_id"] == menu_item["id"] and not c.get("notes"):
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
        per = float(menu.get("prep_time_minutes") or 1) + float(menu.get("cook_time_minutes") or 5)
        qty = max(int(line.get("quantity") or 1), 1)
        duration = per + max(0, qty - 1) * (per * 0.6)
        durations.append(duration)

    if not durations:
        return 0.0

    cfg = config_mod.get_business_config()
    buffer = float(cfg.get("defaultPrepBufferMinutes", 0) or 0)
    return round(max(durations) + buffer, 1)


menu = orders_mod.get_menu(only_available=False)
menu_lookup = {m["id"]: m for m in menu}
unavailable_rows = inventory_mod.get_unavailable_menu_items()
unavailable_lookup = {row["menu_id"]: row for row in unavailable_rows}

if unavailable_rows:
    with st.expander("Availability warnings", expanded=False):
        for row in unavailable_rows:
            blockers = ", ".join(b["ingredient"] for b in row["blocking_ingredients"]) or "ingredient constraints"
            command_card(row["menu_name"], f"Unavailable due to: {blockers}", status="critical")

left, right = st.columns([1.8, 1])

with left:
    by_category = defaultdict(list)
    for m in menu:
        by_category[m.get("category") or "other"].append(m)

    for category in sorted(by_category.keys()):
        section_header(category.title())
        cols = st.columns(2)
        for idx, item in enumerate(by_category[category]):
            with cols[idx % 2]:
                item_status = "healthy" if item["available"] else "critical"
                desc = item.get("description") or ""
                timing = f"Prep {item['prep_time_minutes']}m + Cook {item['cook_time_minutes']}m"
                body = f"${item['price']:.2f}<br/>{desc}<br/>{timing}"
                if not item["available"]:
                    blockers = unavailable_lookup.get(item["id"], {}).get("blocking_ingredients", [])
                    if blockers:
                        body += "<br/>Blocked by: " + ", ".join(b["ingredient"] for b in blockers)
                command_card(item["name"], body, status=item_status)
                if st.button(
                    "Add",
                    key=f"add_{item['id']}",
                    use_container_width=True,
                    disabled=not bool(item["available"]),
                ):
                    add_to_cart(item)
                    st.rerun()

with right:
    section_header("Cart", "Edit quantities and notes before checkout")
    if not st.session_state.cart:
        st.info("Cart is empty.")
    else:
        for idx, line in enumerate(st.session_state.cart):
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{line['quantity']}x {line['name']}**")
                with c2:
                    st.markdown(f"${line['price'] * line['quantity']:.2f}")

                note_key = f"note_{idx}"
                note_val = st.text_input("Notes", value=line.get("notes") or "", key=note_key)
                line["notes"] = note_val or None

                qcols = st.columns(3)
                with qcols[0]:
                    if st.button("-", key=f"dec_{idx}", use_container_width=True):
                        line["quantity"] = max(0, line["quantity"] - 1)
                        if line["quantity"] == 0:
                            remove_line(idx)
                        st.rerun()
                with qcols[1]:
                    if st.button("+", key=f"inc_{idx}", use_container_width=True):
                        line["quantity"] += 1
                        st.rerun()
                with qcols[2]:
                    if st.button("Remove", key=f"del_{idx}", use_container_width=True):
                        remove_line(idx)
                        st.rerun()

    preview_wait = wait_time_preview(menu_lookup, st.session_state.cart)
    c1, c2 = st.columns(2)
    with c1:
        metric_card("Total", f"${cart_total():.2f}")
    with c2:
        metric_card("Est Wait", f"{preview_wait:.1f} min" if preview_wait else "--")

    section_header("Voice Ordering", "Use natural language to adjust cart")
    audio = st.audio_input("Record")
    if audio is not None:
        with st.spinner("Transcribing..."):
            try:
                transcript = agents.transcribe_audio(audio.read(), filename="input.wav")
            except Exception as exc:  # pragma: no cover - depends on API key/runtime
                transcript = None
                st.error(f"Transcription failed: {exc}")

        if transcript:
            st.markdown(f"**You said:** _{transcript}_")
            with st.spinner("Applying changes..."):
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
                if parsed.get("reply"):
                    st.success(parsed["reply"])
                st.rerun()

    if st.session_state.voice_log:
        with st.expander("Voice history"):
            for entry in st.session_state.voice_log[-5:]:
                st.markdown(f"- **{entry['transcript']}** -> {entry['reply']}")

    section_header("Checkout")
    customer_name = st.text_input("Name for the order", value="", placeholder="e.g. Maria")
    can_checkout = bool(st.session_state.cart) and bool(customer_name.strip())

    if st.button("Place Order & Pay", type="primary", use_container_width=True, disabled=not can_checkout):
        payload = [
            {
                "menu_id": line["menu_id"],
                "quantity": line["quantity"],
                "notes": line.get("notes"),
            }
            for line in st.session_state.cart
        ]
        with st.spinner("Charging and placing order..."):
            result = orders_mod.create_order(payload, customer_name=customer_name.strip(), source="kiosk")

        if result.get("ok"):
            st.success(
                f"Order {result['order_number']} placed. Total ${result['total']:.2f}. "
                f"Estimated wait: {result.get('estimated_wait_minutes') or '--'} min."
            )
            if result.get("estimated_ready_at"):
                st.caption(f"Estimated ready at: {result['estimated_ready_at']}")
            if hasattr(st, "page_link"):
                st.page_link("pages/9_🔎_Order_Status.py", label="Check this order on the Order Status page")
            st.session_state.cart = []
            st.session_state.voice_log = []
        else:
            st.error(f"Order failed: {result.get('error', 'unknown_error')}")
            if result.get("missing_ingredients"):
                st.caption("Missing: " + ", ".join(result["missing_ingredients"]))
