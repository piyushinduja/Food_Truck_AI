"""Owner settings page for business and operations configuration."""
from __future__ import annotations

import _path_setup  # noqa: F401

import pandas as pd
import streamlit as st

from backend import config as config_mod
from backend import inventory as inventory_mod
from backend import menu as menu_mod
from backend.bootstrap import ensure_app_ready
from backend.db import get_conn
from backend.theme import apply_global_theme, section_header


st.set_page_config(page_title="Settings — El Camino", page_icon="⚙️", layout="wide")
ensure_app_ready()
apply_global_theme()

section_header("Settings", "Centralized business and operating configuration")

cfg = config_mod.get_business_config()

with st.form("business_settings"):
    b1, b2 = st.columns(2)
    with b1:
        business_name = st.text_input("Business name", value=str(cfg.get("businessName", "El Camino Command")))
        tagline = st.text_input("Tagline", value=str(cfg.get("tagline", "")))
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=1.0, value=float(cfg.get("taxRate", 0.0825)), step=0.001)
        currency = st.text_input("Currency", value=str(cfg.get("currency", "USD")))
    with b2:
        open_status = st.selectbox("Open / Closed", ["open", "closed"], index=0 if str(cfg.get("openStatus", "open")).lower() == "open" else 1)
        truck_location = st.text_input("Truck location", value=str(cfg.get("truckLocation", "")))
        prep_buffer = st.number_input("Default prep buffer minutes", min_value=0.0, value=float(cfg.get("defaultPrepBufferMinutes", 2)), step=0.5)
        expiry_days = st.number_input("Expiry warning days", min_value=0, value=int(cfg.get("expiryWarningDays", 3)), step=1)

    require_approval = st.checkbox(
        "Require human approval for purchasing",
        value=bool(cfg.get("requireHumanApprovalForPurchasing", True)),
    )

    if st.form_submit_button("Save Business Settings", type="primary"):
        config_mod.update_business_config(
            {
                "businessName": business_name,
                "tagline": tagline,
                "taxRate": float(tax_rate),
                "currency": currency,
                "openStatus": open_status,
                "truckLocation": truck_location,
                "defaultPrepBufferMinutes": float(prep_buffer),
                "expiryWarningDays": int(expiry_days),
                "requireHumanApprovalForPurchasing": bool(require_approval),
            }
        )
        st.success("Business settings saved.")
        st.rerun()

section_header("Menu Configuration", "Edit price, availability, and prep/cook timing")
menu_df = pd.DataFrame(menu_mod.list_menu(include_unavailable=True))
if not menu_df.empty:
    menu_edit = st.data_editor(
        menu_df[["id", "name", "category", "price", "prep_time_minutes", "cook_time_minutes", "available", "sort_order"]],
        use_container_width=True,
        hide_index=True,
        key="settings_menu_editor",
        column_config={
            "id": st.column_config.NumberColumn(disabled=True),
            "name": st.column_config.TextColumn(disabled=True),
        },
    )
    if st.button("Save Menu Updates", type="primary"):
        for _, row in menu_edit.iterrows():
            menu_mod.update_menu_item(
                int(row["id"]),
                category=row["category"],
                price=float(row["price"]),
                prep_time_minutes=float(row["prep_time_minutes"]),
                cook_time_minutes=float(row["cook_time_minutes"]),
                available=int(bool(row["available"])),
                sort_order=int(row["sort_order"]),
            )
        menu_mod.recalculate_menu_availability()
        st.success("Menu updates saved.")
        st.rerun()

section_header("Inventory Configuration", "Thresholds, expiry dates, supplier links")
inv_df = pd.DataFrame(inventory_mod.list_inventory())
if not inv_df.empty:
    inv_edit = st.data_editor(
        inv_df[[
            "ingredient",
            "quantity",
            "unit",
            "reorder_threshold",
            "critical_threshold",
            "expiration_date",
            "supplier_id",
            "category",
            "cost_per_unit",
        ]],
        use_container_width=True,
        hide_index=True,
        key="settings_inventory_editor",
        column_config={
            "ingredient": st.column_config.TextColumn(disabled=True),
        },
    )
    if st.button("Save Inventory Configuration", type="primary"):
        for _, row in inv_edit.iterrows():
            inventory_mod.update_inventory_item(
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
        st.success("Inventory configuration saved.")
        st.rerun()

section_header("Suppliers", "Maintain supplier directory")
with get_conn() as conn:
    suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()

sup_df = pd.DataFrame([dict(s) for s in suppliers])
if not sup_df.empty:
    sup_edit = st.data_editor(
        sup_df,
        use_container_width=True,
        hide_index=True,
        key="settings_suppliers_editor",
        column_config={"id": st.column_config.NumberColumn(disabled=True)},
    )
    if st.button("Save Supplier Updates", type="primary"):
        with get_conn() as conn:
            for _, row in sup_edit.iterrows():
                conn.execute(
                    """
                    UPDATE suppliers
                    SET name = ?, type = ?, website = ?, contact_info = ?, estimated_delivery_time = ?, notes = ?
                    WHERE id = ?
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
        st.success("Supplier records updated.")
        st.rerun()

with st.form("new_supplier"):
    st.markdown("**Add Supplier**")
    s1, s2 = st.columns(2)
    with s1:
        new_name = st.text_input("Name")
        new_type = st.text_input("Type")
        new_website = st.text_input("Website")
    with s2:
        new_contact = st.text_input("Contact info")
        new_eta = st.text_input("Estimated delivery time")
        new_notes = st.text_area("Notes", height=80)

    if st.form_submit_button("Add Supplier"):
        if not new_name.strip():
            st.error("Supplier name is required.")
        else:
            with get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO suppliers (name, type, website, contact_info, estimated_delivery_time, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        type = excluded.type,
                        website = excluded.website,
                        contact_info = excluded.contact_info,
                        estimated_delivery_time = excluded.estimated_delivery_time,
                        notes = excluded.notes
                    """,
                    (new_name.strip(), new_type, new_website, new_contact, new_eta, new_notes),
                )
            st.success("Supplier added/updated.")
            st.rerun()

section_header("Theme Tokens", "Centralized command-center color tokens")
with get_conn() as conn:
    theme_rows = conn.execute("SELECT key, value FROM theme_config ORDER BY key").fetchall()

theme_df = pd.DataFrame([dict(r) for r in theme_rows])
if not theme_df.empty:
    theme_edit = st.data_editor(theme_df, use_container_width=True, hide_index=True, key="settings_theme_editor")
    if st.button("Save Theme Tokens", type="primary"):
        with get_conn() as conn:
            for _, row in theme_edit.iterrows():
                conn.execute(
                    """
                    INSERT INTO theme_config (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (row["key"], row["value"]),
                )
        st.success("Theme tokens updated. Reload pages to see full effect.")
        st.rerun()
