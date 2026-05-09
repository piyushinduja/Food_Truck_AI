"""Inventory page — stock levels, low-stock alerts, restock from supplier."""
import _path_setup  # noqa: F401
import streamlit as st
import pandas as pd

from backend import inventory as inv_mod


st.set_page_config(page_title="Inventory — El Camino", page_icon="📦", layout="wide")
st.title("📦 Inventory")
st.caption("Stock levels deduct automatically with each order. Reorder from Walmart (mocked).")


inv = inv_mod.list_inventory()
low = inv_mod.get_low_stock()
suggestions = inv_mod.suggest_restocks()

# Summary cards
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Ingredients Tracked", len(inv))
with c2:
    st.metric("Low Stock Items", len(low), delta=("⚠️ needs attention" if low else "✓ all good"), delta_color="off")
with c3:
    inv_value = sum(i["quantity"] * i["cost_per_unit"] for i in inv)
    st.metric("Inventory Value", f"${inv_value:,.2f}")


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


# Restock history
restocks = inv_mod.list_restocks(limit=10)
if restocks:
    st.markdown("### Recent Restock Orders")
    rdf = pd.DataFrame(restocks)
    rdf = rdf[["created_at", "ingredient", "quantity", "unit", "cost", "supplier", "status"]]
    rdf.columns = ["Time", "Ingredient", "Qty", "Unit", "Cost ($)", "Supplier", "Status"]
    st.dataframe(rdf, width='stretch', hide_index=True)
