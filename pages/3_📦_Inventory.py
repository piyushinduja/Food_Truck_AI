"""Inventory page — stock levels, low-stock alerts, restock from supplier."""
import _path_setup  # noqa: F401
import streamlit as st
import pandas as pd

from backend import inventory as inv_mod, agents


st.set_page_config(page_title="Inventory — El Camino", page_icon="📦", layout="wide")
st.title("📦 Inventory")
st.caption("Stock levels deduct automatically with each order. Reorder from Walmart (mocked).")


inv = inv_mod.list_inventory()
low = inv_mod.get_low_stock()
suggestions = inv_mod.suggest_restocks()

# Session state for AI restock cart
if "ai_cart" not in st.session_state:
    st.session_state.ai_cart = None  # list of order dicts when generated

# Summary cards
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Ingredients Tracked", len(inv))
with c2:
    st.metric("Low Stock Items", len(low), delta=("⚠️ needs attention" if low else "✓ all good"), delta_color="off")
with c3:
    inv_value = sum(i["quantity"] * i["cost_per_unit"] for i in inv)
    st.metric("Inventory Value", f"${inv_value:,.2f}")


# AI Restock Cart
st.markdown("---")
st.markdown("### 🤖 AI Restock Cart")
st.caption("AI analyzes your stock levels and sales velocity, then proposes a shopping cart. You approve before anything is ordered.")

gen_col, clear_col = st.columns([2, 1])
with gen_col:
    if st.button("Generate AI Restock Plan", type="primary", use_container_width=True):
        with st.spinner("Analyzing inventory and sales velocity..."):
            try:
                stockout_data = inv_mod.predict_stockouts(days=7)
                cart = agents.generate_restock_cart(low, stockout_data)
                if cart:
                    st.session_state.ai_cart = cart
                else:
                    st.info("AI found nothing urgent to restock right now.")
                    st.session_state.ai_cart = []
            except Exception as e:
                st.error(f"Failed to generate plan: {e}")
with clear_col:
    if st.button("Clear Cart", use_container_width=True):
        st.session_state.ai_cart = None
        st.rerun()

if st.session_state.ai_cart:
    cart = st.session_state.ai_cart

    priority_emoji = {"urgent": "🔴", "soon": "🟡", "optional": "🔵"}

    st.markdown("Review the AI's recommendations below. Edit quantities if needed, then approve the items you want to order.")

    approved_items = []
    for i, item in enumerate(cart):
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([0.4, 2.5, 1.2, 1.2, 0.8])
            with c1:
                approved = st.checkbox(
                    "Approve",
                    value=item["priority"] in ("urgent", "soon"),
                    key=f"approve_{i}",
                    label_visibility="collapsed",
                )
            with c2:
                badge = priority_emoji.get(item["priority"], "⚪")
                st.markdown(f"**{badge} {item['ingredient']}**")
                st.caption(item["reasoning"])
            with c3:
                qty = st.number_input(
                    "Qty",
                    min_value=0.0,
                    value=float(item["suggested_qty"]),
                    step=10.0,
                    key=f"qty_{i}",
                    label_visibility="collapsed",
                )
                st.caption(f"{item['unit']}")
            with c4:
                cost = item["cost_per_unit"] * qty * 1.15
                st.markdown(f"**${cost:.2f}**")
                st.caption("est. cost")
            with c5:
                st.markdown(f"`{item['priority']}`")

            if approved and qty > 0:
                approved_items.append({"ingredient": item["ingredient"], "qty": qty})

    if approved_items:
        total_est = sum(
            item["estimated_cost"] * (
                st.session_state.get(f"qty_{i}", item["suggested_qty"]) / item["suggested_qty"]
                if item["suggested_qty"] > 0 else 1
            )
            for i, item in enumerate(cart)
            if st.session_state.get(f"approve_{i}", False)
        )
        st.markdown(f"**{len(approved_items)} item(s) selected · Est. total: ${total_est:.2f}**")

        if st.button("Place Approved Orders", type="primary", use_container_width=True):
            results = []
            errors = []
            for a in approved_items:
                r = inv_mod.place_restock_order(a["ingredient"], a["qty"])
                if r["ok"]:
                    results.append(r)
                else:
                    errors.append(f"{a['ingredient']}: {r.get('error')}")

            if results:
                st.success(f"✓ Placed {len(results)} order(s)")
                for r in results:
                    st.markdown(f"- **{r['ingredient']}** — {r['quantity']} {r['unit']} · ${r['cost']:.2f} · `{r['confirmation_id']}`")
            if errors:
                for e in errors:
                    st.error(e)

            st.session_state.ai_cart = None
            st.rerun()
    else:
        st.caption("Check the boxes next to items you want to order.")

elif st.session_state.ai_cart is not None and len(st.session_state.ai_cart) == 0:
    st.success("Everything looks well-stocked. No urgent restocks needed.")


# Low-stock alerts with one-click restock
if suggestions:
    st.markdown("### ⚠️ Low Stock — Suggested Restocks")
    for s in suggestions:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 1])
            with cols[0]:
                st.markdown(f"**{s['ingredient']}**")
                st.caption(f"Current: {s['current']} {s['unit']}")
            with cols[1]:
                st.markdown(f"Suggested: **{s['suggested_qty']} {s['unit']}**")
            with cols[2]:
                st.markdown(f"Est. cost: **${s['estimated_cost']:.2f}**")
            with cols[3]:
                if st.button("Order", key=f"restock_{s['ingredient']}", type="primary", width='stretch'):
                    result = inv_mod.place_restock_order(s["ingredient"], s["suggested_qty"])
                    if result["ok"]:
                        st.success(f"Ordered. Confirmation: {result['confirmation_id']}")
                        st.rerun()
                    else:
                        st.error(result.get("error", "failed"))


st.markdown("---")
st.markdown("### Full Inventory")

df = pd.DataFrame(inv)
df["status"] = df.apply(
    lambda r: "🔴 Low" if r["quantity"] <= r["reorder_threshold"] else "🟢 OK", axis=1
)
df["value"] = (df["quantity"] * df["cost_per_unit"]).round(2)
df = df[["status", "ingredient", "quantity", "unit", "reorder_threshold", "cost_per_unit", "value"]]
df.columns = ["Status", "Ingredient", "Qty", "Unit", "Reorder At", "Cost/Unit", "Value ($)"]

st.dataframe(df, width='stretch', hide_index=True)


# Manual restock — pick anything
st.markdown("---")
st.markdown("### Manual Restock")
manual_cols = st.columns([3, 2, 1])
with manual_cols[0]:
    selected = st.selectbox("Ingredient", [i["ingredient"] for i in inv])
with manual_cols[1]:
    qty = st.number_input("Quantity", min_value=0.0, value=100.0, step=10.0)
with manual_cols[2]:
    st.markdown("&nbsp;")
    if st.button("Place Order", width='stretch'):
        result = inv_mod.place_restock_order(selected, qty)
        if result["ok"]:
            st.success(f"Ordered {qty} {result['unit']} of {selected} — ${result['cost']:.2f} ({result['confirmation_id']})")
            st.rerun()
        else:
            st.error(result.get("error"))


# Stockout Forecast
st.markdown("---")
st.markdown("### 🔮 Stockout Forecast")
st.caption("Based on consumption velocity from the last 7 days of orders.")

stockouts = inv_mod.predict_stockouts(days=7)
active_stockouts = [s for s in stockouts if s["days_remaining"] is not None]

if not active_stockouts:
    st.info("No velocity data yet — place some orders to build forecasts.")
else:
    def days_label(d):
        if d is None:
            return "—"
        if d < 2:
            return f"🔴 {d}d"
        if d < 5:
            return f"🟡 {d}d"
        return f"🟢 {d}d"

    sdf = pd.DataFrame([
        {
            "Ingredient": s["ingredient"],
            "On Hand": f"{s['current_qty']} {s['unit']}",
            "Daily Use": f"{s['daily_velocity']} {s['unit']}/day",
            "Days Remaining": days_label(s["days_remaining"]),
        }
        for s in stockouts
    ])
    st.dataframe(sdf, width='stretch', hide_index=True)

    if st.button("Analyze with AI", type="primary"):
        with st.spinner("Asking Groq to assess your stock risks..."):
            try:
                analysis = agents.analyze_stockouts(stockouts)
                st.markdown(analysis)
            except Exception as e:
                st.error(f"Analysis failed: {e}")


# Restock history
restocks = inv_mod.list_restocks(limit=10)
if restocks:
    st.markdown("### Recent Restock Orders")
    rdf = pd.DataFrame(restocks)
    rdf = rdf[["created_at", "ingredient", "quantity", "unit", "cost", "supplier", "status"]]
    rdf.columns = ["Time", "Ingredient", "Qty", "Unit", "Cost ($)", "Supplier", "Status"]
    st.dataframe(rdf, width='stretch', hide_index=True)
