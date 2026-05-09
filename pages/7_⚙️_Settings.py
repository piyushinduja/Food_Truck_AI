"""Owner settings page."""
from __future__ import annotations

import _path_setup  # noqa: F401

import pandas as pd
import streamlit as st

from backend import config, inventory, menu, nutrition
from backend.autopilot import get_autonomy_mode, set_autonomy_mode
from backend.bootstrap import ensure_app_ready
from backend.db import get_conn
from backend.ui_components import VIEW_OWNER, enforce_view_mode, render_app_shell, render_section_header


st.set_page_config(page_title="Settings — El Camino", page_icon="⚙️", layout="wide")
ensure_app_ready()
render_app_shell(VIEW_OWNER)
enforce_view_mode(VIEW_OWNER)

render_section_header("Settings", "Business profile, menu, inventory, suppliers, theme, autonomy")
cfg = config.get_business_config()

with st.form("business_settings"):
    c1, c2, c3 = st.columns(3)
    with c1:
        business_name = st.text_input("Business name", value=str(cfg.get("businessName", "El Camino")))
        tagline = st.text_input("Tagline", value=str(cfg.get("tagline", "")))
        truck_location = st.text_input("Truck location", value=str(cfg.get("truckLocation", "")))
    with c2:
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=1.0, value=float(cfg.get("taxRate", 0.0825)), step=0.001)
        open_status = st.selectbox("Open/Closed", ["open", "closed"], index=0 if str(cfg.get("openStatus", "open")).lower() == "open" else 1)
        prep_buffer = st.number_input("Default prep buffer (min)", min_value=0.0, value=float(cfg.get("defaultPrepBufferMinutes", 2)), step=0.5)
    with c3:
        expiry_days = st.number_input("Expiry warning days", min_value=0, value=int(cfg.get("expiryWarningDays", 3)), step=1)
        require_approval = st.checkbox("Require human approval for purchasing", value=bool(cfg.get("requireHumanApprovalForPurchasing", True)))
        autonomy_mode = st.selectbox("Autonomy mode", ["manual", "assist", "full autopilot"], index=["manual", "assist", "full autopilot"].index(get_autonomy_mode()))

    rush_threshold = st.number_input("Rush mode threshold (active orders)", min_value=1, value=int(cfg.get("rushModeOrderThreshold", 6)), step=1)
    notify_enabled = st.checkbox("Enable operator notifications", value=bool(cfg.get("notificationsEnabled", True)))

    if st.form_submit_button("Save Business Settings", type="primary"):
        config.update_business_config(
            {
                "businessName": business_name,
                "tagline": tagline,
                "truckLocation": truck_location,
                "taxRate": float(tax_rate),
                "openStatus": open_status,
                "defaultPrepBufferMinutes": float(prep_buffer),
                "expiryWarningDays": int(expiry_days),
                "requireHumanApprovalForPurchasing": bool(require_approval),
                "rushModeOrderThreshold": int(rush_threshold),
                "notificationsEnabled": bool(notify_enabled),
            }
        )
        set_autonomy_mode(autonomy_mode)
        st.success("Settings saved")
        st.rerun()

render_section_header("Menu")
menu_df = pd.DataFrame(menu.list_menu(include_unavailable=True))
if not menu_df.empty:
    edit = st.data_editor(
        menu_df[["id", "name", "category", "price", "prep_time_minutes", "cook_time_minutes", "available", "sort_order"]],
        hide_index=True,
        use_container_width=True,
        key="settings_menu",
    )
    if st.button("Save Menu", type="primary"):
        for _, row in edit.iterrows():
            menu.update_menu_item(
                int(row["id"]),
                category=row["category"],
                price=float(row["price"]),
                prep_time_minutes=float(row["prep_time_minutes"]),
                cook_time_minutes=float(row["cook_time_minutes"]),
                available=int(bool(row["available"])),
                sort_order=int(row["sort_order"]),
            )
        menu.recalculate_menu_availability()
        st.success("Menu updated")
        st.rerun()

render_section_header("Menu Nutrition")
nutrition_df = pd.DataFrame(nutrition.list_menu_with_nutrition(include_unavailable=True))
if not nutrition_df.empty:
    edit = st.data_editor(
        nutrition_df[
            [
                "menu_item_id",
                "name",
                "calories",
                "protein_g",
                "carbs_g",
                "fat_g",
                "fiber_g",
                "sugar_g",
                "sodium_mg",
                "source",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        disabled=["menu_item_id", "name", "source"],
        key="settings_menu_nutrition",
    )
    if st.button("Save Nutrition", type="primary"):
        for _, row in edit.iterrows():
            nutrition.update_menu_nutrition(
                int(row["menu_item_id"]),
                {
                    "calories": float(row["calories"]),
                    "protein_g": float(row["protein_g"]),
                    "carbs_g": float(row["carbs_g"]),
                    "fat_g": float(row["fat_g"]),
                    "fiber_g": float(row["fiber_g"]),
                    "sugar_g": float(row["sugar_g"]),
                    "sodium_mg": float(row["sodium_mg"]),
                    "source": "owner_edit",
                },
            )
        st.success("Nutrition updated")
        st.rerun()
else:
    st.warning("No menu nutrition records found. Reset or reseed demo data.")

render_section_header("Inventory")
inv_df = pd.DataFrame(inventory.list_inventory())
if not inv_df.empty:
    edit = st.data_editor(
        inv_df[["ingredient", "quantity", "unit", "reorder_threshold", "critical_threshold", "expiration_date", "supplier_id", "category", "cost_per_unit"]],
        hide_index=True,
        use_container_width=True,
        key="settings_inventory",
    )
    if st.button("Save Inventory", type="primary"):
        for _, row in edit.iterrows():
            inventory.update_inventory_item(
                ingredient=row["ingredient"],
                quantity=float(row["quantity"]),
                unit=row["unit"],
                reorder_threshold=float(row["reorder_threshold"]),
                critical_threshold=float(row["critical_threshold"]),
                expiration_date=(row["expiration_date"] or None),
                supplier_id=(int(row["supplier_id"]) if pd.notna(row["supplier_id"]) else None),
                category=row["category"],
                cost_per_unit=float(row["cost_per_unit"]),
            )
        st.success("Inventory updated")
        st.rerun()

render_section_header("Suppliers")
with get_conn() as conn:
    suppliers = [dict(row) for row in conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()]
sup_df = pd.DataFrame(suppliers)
if not sup_df.empty:
    edit = st.data_editor(sup_df, hide_index=True, use_container_width=True, key="settings_suppliers")
    if st.button("Save Suppliers", type="primary"):
        with get_conn() as conn:
            for _, row in edit.iterrows():
                conn.execute(
                    """
                    UPDATE suppliers
                    SET name=?, type=?, website=?, contact_info=?, estimated_delivery_time=?, notes=?
                    WHERE id=?
                    """,
                    (
                        row["name"],
                        row.get("type"),
                        row.get("website"),
                        row.get("contact_info"),
                        row.get("estimated_delivery_time"),
                        row.get("notes"),
                        int(row["id"]),
                    ),
                )
        st.success("Suppliers updated")
        st.rerun()

render_section_header("Theme Tokens")
with get_conn() as conn:
    theme_rows = [dict(row) for row in conn.execute("SELECT key, value FROM theme_config ORDER BY key").fetchall()]
if theme_rows:
    theme_df = pd.DataFrame(theme_rows)
    edit = st.data_editor(theme_df, hide_index=True, use_container_width=True, key="settings_theme")
    if st.button("Save Theme", type="primary"):
        with get_conn() as conn:
            for _, row in edit.iterrows():
                conn.execute(
                    """
                    INSERT INTO theme_config (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (row["key"], row["value"]),
                )
        st.success("Theme tokens updated")
        st.rerun()
