"""Customer macro profile, dashboard, smart ordering, and history."""
from __future__ import annotations

import _path_setup  # noqa: F401
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from backend import agents, macro_charts, macro_recommendations, macros, nutrition
from backend.bootstrap import ensure_app_ready
from backend.ui_components import VIEW_CUSTOMER, enforce_view_mode, render_app_shell, render_metric_card, render_section_header


st.set_page_config(page_title="Macros — El Camino", page_icon="🥗", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_CUSTOMER)
enforce_view_mode(VIEW_CUSTOMER)

TODAY = date.today().isoformat()


def _profile_options() -> tuple[list[str], list[dict]]:
    profiles = macros.list_customer_profiles()
    return [f"{p['customer_name']} #{p['id']}" for p in profiles], profiles


def _select_profile(key: str) -> dict | None:
    labels, profiles = _profile_options()
    if not profiles:
        return None
    current_id = st.session_state.get("selected_customer_id")
    default_index = 0
    for idx, profile in enumerate(profiles):
        if profile["id"] == current_id:
            default_index = idx
            break
    label = st.selectbox("Customer profile", labels, index=default_index, key=key)
    profile = profiles[labels.index(label)]
    st.session_state["selected_customer_id"] = profile["id"]
    return profile


def _save_recommendation_to_cart(recommendation: dict) -> None:
    cart = list(st.session_state.get("cart", []))
    menu = {item["menu_item_id"]: item for item in nutrition.list_menu_with_nutrition(include_unavailable=True)}
    for item in recommendation.get("recommended_items", []):
        menu_item = menu.get(item["menu_id"])
        if not menu_item:
            continue
        cart.append(
            {
                "menu_id": item["menu_id"],
                "name": item["name"],
                "price": float(menu_item["price"]),
                "quantity": int(item.get("quantity") or 1),
                "notes": None,
            }
        )
    st.session_state["cart"] = cart


render_section_header("Customer Macros", "Personalized ordering from real El Camino nutrition data")

profile_tab, dashboard_tab, order_tab, history_tab = st.tabs(
    ["Macro Profile", "Macro Dashboard", "Build My Macro Order", "Macro History"]
)

with profile_tab:
    render_section_header("Macro Profile")
    existing = _select_profile("profile_select_profile")
    with st.form("macro_profile_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("Name", value=(existing or {}).get("customer_name", ""))
            phone = st.text_input("Phone", value=(existing or {}).get("phone") or "")
            email = st.text_input("Email", value=(existing or {}).get("email") or "")
        with c2:
            height_cm = st.number_input("Height (cm)", min_value=90.0, max_value=230.0, value=float((existing or {}).get("height_cm") or 175), step=1.0)
            weight_kg = st.number_input("Weight (kg)", min_value=35.0, max_value=220.0, value=float((existing or {}).get("weight_kg") or 75), step=0.5)
            age = st.number_input("Age", min_value=13, max_value=100, value=int((existing or {}).get("age") or 30), step=1)
        with c3:
            sex_options = ["unspecified", "male", "female"]
            sex = st.selectbox("Sex", sex_options, index=sex_options.index((existing or {}).get("sex") or "unspecified") if (existing or {}).get("sex") in sex_options else 0)
            activity_options = ["sedentary", "light", "moderate", "active", "very_active"]
            activity = st.selectbox("Activity level", activity_options, index=activity_options.index((existing or {}).get("activity_level") or "moderate") if (existing or {}).get("activity_level") in activity_options else 2)
            goal_options = ["maintain", "lose weight", "gain muscle", "high protein", "custom macros"]
            goal = st.selectbox("Goal", goal_options, index=goal_options.index((existing or {}).get("goal") or "maintain") if (existing or {}).get("goal") in goal_options else 0)
        target_existing = macros.get_macro_targets(existing["id"], TODAY) if existing else None
        custom_cols = st.columns(4)
        with custom_cols[0]:
            custom_calories = st.number_input("Custom calories", min_value=0.0, value=float((target_existing or {}).get("calories") or 0), step=25.0, disabled=goal != "custom macros")
        with custom_cols[1]:
            custom_protein = st.number_input("Custom protein g", min_value=0.0, value=float((target_existing or {}).get("protein_g") or 0), step=5.0, disabled=goal != "custom macros")
        with custom_cols[2]:
            custom_carbs = st.number_input("Custom carbs g", min_value=0.0, value=float((target_existing or {}).get("carbs_g") or 0), step=5.0, disabled=goal != "custom macros")
        with custom_cols[3]:
            custom_fat = st.number_input("Custom fat g", min_value=0.0, value=float((target_existing or {}).get("fat_g") or 0), step=5.0, disabled=goal != "custom macros")

        save_profile = st.form_submit_button("Save Macro Goals", type="primary")

    if save_profile:
        profile_fields = {
            "email": email or None,
            "height_cm": float(height_cm),
            "weight_kg": float(weight_kg),
            "age": int(age),
            "sex": sex,
            "activity_level": activity,
            "goal": goal,
        }
        profile = macros.find_or_create_customer_by_name_phone(name, phone or None, **profile_fields)
        if goal == "custom macros":
            targets = {
                "calories": float(custom_calories),
                "protein_g": float(custom_protein),
                "carbs_g": float(custom_carbs),
                "fat_g": float(custom_fat),
                "source": "customer_custom",
            }
        else:
            targets = macros.calculate_macro_targets(profile)
        macros.save_macro_targets(profile["id"], TODAY, targets)
        st.session_state["selected_customer_id"] = profile["id"]
        st.success("Macro profile and targets saved.")
        st.rerun()

    selected = existing
    if selected:
        try:
            targets = macros.calculate_macro_targets(selected)
            cols = st.columns(4)
            with cols[0]:
                render_metric_card("Calories", f"{targets['calories']:.0f}")
            with cols[1]:
                render_metric_card("Protein", f"{targets['protein_g']:.0f}g")
            with cols[2]:
                render_metric_card("Carbs", f"{targets['carbs_g']:.0f}g")
            with cols[3]:
                render_metric_card("Fat", f"{targets['fat_g']:.0f}g")
        except ValueError:
            st.info("Save height, weight, and age to calculate targets.")

with dashboard_tab:
    profile = _select_profile("dashboard_select_profile")
    if not profile:
        st.info("Create a macro profile first.")
    else:
        summary = macros.get_daily_macro_summary(profile["id"], TODAY)
        progress = macro_charts.get_macro_progress_data(profile["id"], TODAY)
        cols = st.columns(4)
        for idx, row in enumerate(progress):
            with cols[idx]:
                render_metric_card(
                    row["macro"],
                    f"{row['consumed']:.0f} / {row['target']:.0f}",
                    subtext=f"{row['remaining']:.0f} remaining",
                    status="critical" if row["status"] == "over" else "healthy",
                )
                st.progress(min(float(row["percent"]) / 100, 1.0))

        left, right = st.columns(2, gap="large")
        with left:
            pie_df = pd.DataFrame(macro_charts.get_macro_pie_data(profile["id"], TODAY))
            if float(pie_df["grams"].sum()) > 0:
                chart = (
                    alt.Chart(pie_df)
                    .mark_arc(innerRadius=52)
                    .encode(theta="calories:Q", color=alt.Color("macro:N", scale=alt.Scale(range=["#D91F26", "#B8B8B8", "#2F8F57"])), tooltip=["macro", "grams", "calories"])
                    .properties(height=280)
                )
                st.altair_chart(chart, width='stretch')
            else:
                st.caption("No macro intake logged today.")
        with right:
            hist = pd.DataFrame(macro_charts.get_macro_history_chart_data(profile["id"], 7))
            trend = (
                alt.Chart(hist)
                .mark_bar(color="#D91F26")
                .encode(x=alt.X("summary_date:N", title=None), y=alt.Y("calories_consumed:Q", title="Calories"), tooltip=["summary_date", "calories_consumed", "protein_consumed_g"])
                .properties(height=280)
            )
            st.altair_chart(trend, width='stretch')

        render_section_header("Recent Macro Orders")
        recent = macros.get_recent_macro_orders(profile["id"], days=7)
        if recent:
            st.dataframe(pd.DataFrame(recent), width='stretch', hide_index=True)
        else:
            st.caption("No macro-tracked orders yet.")

with order_tab:
    profile = _select_profile("order_select_profile")
    if not profile:
        st.info("Create a macro profile first.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            build_scope = st.selectbox("Build", ["one meal", "whole day"])
        with c2:
            strategy = st.selectbox(
                "Strategy",
                [
                    "balanced",
                    "use today remaining",
                    "stay under remaining macros",
                    "hit protein target",
                    "high protein",
                    "lower carb",
                    "lower fat",
                    "use yesterday missed",
                ],
            )
        with c3:
            use_ai = st.checkbox("AI explanation", value=False)

        if st.button("Build My Macro Order", type="primary"):
            if build_scope == "one meal":
                result = macro_recommendations.recommend_meal_for_macros(profile["id"], TODAY, strategy)
            else:
                result = macro_recommendations.recommend_day_for_macros(profile["id"], TODAY, strategy)
            st.session_state["macro_recommendation"] = result.get("recommendation")
            st.session_state["macro_recommendation_scope"] = build_scope
            st.session_state["macro_recommendation_ai"] = use_ai

        recommendation = st.session_state.get("macro_recommendation")
        if recommendation:
            items = recommendation.get("recommended_items", [])
            render_section_header("Recommended Order")
            st.markdown(", ".join(f"**{item['name']}**" for item in items))
            cols = st.columns(4)
            with cols[0]:
                render_metric_card("Calories", f"{recommendation['calories']:.0f}")
            with cols[1]:
                render_metric_card("Protein", f"{recommendation['protein_g']:.0f}g")
            with cols[2]:
                render_metric_card("Carbs", f"{recommendation['carbs_g']:.0f}g")
            with cols[3]:
                render_metric_card("Fat", f"{recommendation['fat_g']:.0f}g")

            if recommendation.get("groups"):
                for group in recommendation["groups"]:
                    st.markdown(f"**{group['label']}**: " + ", ".join(item["name"] for item in group["items"]))
                if not recommendation.get("can_satisfy_full_day", True):
                    st.warning("The current food-truck menu cannot perfectly satisfy the full-day target; this is the closest realistic combination.")

            if st.session_state.get("macro_recommendation_ai"):
                try:
                    ai = agents.explain_macro_order_recommendation(profile["id"], recommendation)
                    st.info(ai["reply"])
                except Exception as exc:
                    st.warning(f"AI explanation unavailable: {exc}")

            if st.button("Add Recommended Order to Cart", width='stretch'):
                _save_recommendation_to_cart(recommendation)
                st.success("Recommended items added to cart.")

with history_tab:
    profile = _select_profile("history_select_profile")
    if not profile:
        st.info("Create a macro profile first.")
    else:
        days = st.selectbox("History window", [1, 2, 7, 30], index=2, format_func=lambda d: "Today" if d == 1 else "Yesterday + today" if d == 2 else f"Last {d} days")
        history = pd.DataFrame(macros.get_macro_history(profile["id"], days=days))
        st.dataframe(history, width='stretch', hide_index=True)
        if not history.empty:
            protein = (
                alt.Chart(history)
                .mark_line(point=True, color="#2F8F57")
                .encode(x=alt.X("summary_date:N", title=None), y=alt.Y("protein_consumed_g:Q", title="Protein g"), tooltip=["summary_date", "protein_consumed_g", "protein_target_g"])
                .properties(height=260)
            )
            st.altair_chart(protein, width='stretch')

        if st.button("What should I order later today?"):
            try:
                ai = agents.macro_suggestion_agent(profile["id"], TODAY)
                st.info(ai["reply"])
            except Exception as exc:
                st.warning(f"AI suggestion unavailable: {exc}")
