"""Sales page — item rankings and category breakdown."""
import _path_setup  # noqa: F401
import streamlit as st
import pandas as pd
import altair as alt

from backend import analytics


st.set_page_config(page_title="Sales — El Camino", page_icon="📊", layout="wide")
st.title("📊 Sales Analyzer")
st.caption("What's selling, what's not.")


days = st.sidebar.slider("Time window (days)", 1, 60, 7)


sales = analytics.sales_by_item(days=days)

if not sales:
    st.info(f"No sales in the last {days} day(s). Place some orders to see data.")
else:
    df = pd.DataFrame(sales)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Top Seller", df.iloc[0]["name"], f"{int(df.iloc[0]['units_sold'])} sold")
    with c2:
        st.metric("Total Items Sold", int(df["units_sold"].sum()))

    # Bar chart of units sold
    st.markdown(f"### Units Sold (last {days}d)")
    chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("units_sold:Q", title="Units"),
        y=alt.Y("name:N", sort="-x", title=None),
        color=alt.Color("category:N", scale=alt.Scale(scheme="orangered")),
        tooltip=["name", "units_sold", "revenue"],
    ).properties(height=350)
    st.altair_chart(chart, width='stretch')

    # Table
    st.markdown("### Detail")
    table = df.copy()
    table["revenue"] = table["revenue"].round(2)
    table.columns = ["Item", "Category", "Units Sold", "Revenue ($)"]
    st.dataframe(table, width='stretch', hide_index=True)


# Category breakdown
st.markdown("---")
st.markdown(f"### Revenue by Category (last {days}d)")
cat = analytics.revenue_by_category(days=days)
if cat:
    cdf = pd.DataFrame(cat)
    pie = alt.Chart(cdf).mark_arc(innerRadius=60).encode(
        theta="revenue:Q",
        color=alt.Color("category:N", scale=alt.Scale(scheme="orangered")),
        tooltip=["category", "revenue", "units"],
    ).properties(height=300)
    st.altair_chart(pie, width='stretch')
else:
    st.caption("No category data yet.")
