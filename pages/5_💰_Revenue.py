"""Revenue page — daily revenue trends."""
import _path_setup  # noqa: F401
import streamlit as st
import pandas as pd
import altair as alt

from backend import analytics


st.set_page_config(page_title="Revenue — El Camino", page_icon="💰", layout="wide")
st.title("💰 Revenue Analyzer")


days = st.sidebar.slider("Time window (days)", 7, 90, 30)

today = analytics.today_summary()
daily = analytics.revenue_by_day(days=days)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Today", f"${today['revenue']:.2f}", f"{today['num_orders']} orders")
with c2:
    total = sum(d["revenue"] for d in daily) if daily else 0
    st.metric(f"Last {days}d Revenue", f"${total:,.2f}")
with c3:
    avg = (total / len(daily)) if daily else 0
    st.metric("Avg / Day", f"${avg:.2f}")


if not daily:
    st.info("No revenue data yet.")
else:
    df = pd.DataFrame(daily)
    df["day"] = pd.to_datetime(df["day"])

    st.markdown(f"### Daily Revenue (last {days}d)")
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("day:T", title="Day"),
        y=alt.Y("revenue:Q", title="Revenue ($)"),
        color=alt.value("#d4471a"),
        tooltip=[
            alt.Tooltip("day:T", title="Date"),
            alt.Tooltip("revenue:Q", title="Revenue", format="$.2f"),
            alt.Tooltip("num_orders:Q", title="Orders"),
        ],
    ).properties(height=350)
    st.altair_chart(bars, use_container_width=True)

    st.markdown("### Detail")
    table = df.copy()
    table["revenue"] = table["revenue"].round(2)
    table.columns = ["Day", "# Orders", "Revenue ($)"]
    st.dataframe(table, use_container_width=True, hide_index=True)
