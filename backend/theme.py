"""Centralized UI theme helpers for Streamlit pages."""
from __future__ import annotations

from typing import Any

import streamlit as st

from .db import get_conn, init_db
from .theme_tokens import DEFAULT_THEME_TOKENS


def get_theme_tokens() -> dict[str, str]:
    init_db()
    tokens = dict(DEFAULT_THEME_TOKENS)
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM theme_config").fetchall()

    for row in rows:
        if row["key"] in tokens:
            tokens[row["key"]] = row["value"]

    # ensure editability of all defaults
    with get_conn() as conn:
        for key, value in DEFAULT_THEME_TOKENS.items():
            conn.execute(
                """
                INSERT INTO theme_config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value),
            )

    return tokens


def _status_color(tokens: dict[str, str], status: str | None) -> str:
    if not status:
        return tokens["text_secondary"]
    key = status.lower()
    if key in {"healthy", "ok", "success", "ready", "completed"}:
        return tokens["success"]
    if key in {"warning", "attention", "pending", "preparing", "low", "expires_soon", "expires_today"}:
        return tokens["warning"]
    if key in {"critical", "danger", "out", "expired", "late", "cancelled", "rejected"}:
        return tokens["danger_red"]
    return tokens["text_secondary"]


def apply_global_theme() -> None:
    tokens = get_theme_tokens()
    st.markdown(
        f"""
        <style>
            :root {{
                --ec-bg: {tokens['background']};
                --ec-page-bg: {tokens['background']};
                --ec-sidebar-bg: #0B0B0B;
                --ec-surface: {tokens['surface']};
                --ec-card: {tokens['surface']};
                --ec-surface-elev: {tokens['surface_elevated']};
                --ec-card-elev: {tokens['surface_elevated']};
                --ec-text: {tokens['text_primary']};
                --ec-text-secondary: {tokens['text_secondary']};
                --ec-text-muted: {tokens['text_secondary']};
                --ec-border: {tokens['border']};
                --ec-red: {tokens['primary_red']};
                --ec-red-hover: #F12A32;
                --ec-red-dark: #7A1014;
                --ec-danger: {tokens['danger_red']};
                --ec-warning: {tokens['warning']};
                --ec-success: {tokens['success']};
            }}
            #MainMenu {{ visibility: hidden; }}
            footer {{ visibility: hidden; }}
            header[data-testid="stHeader"] {{
                background: transparent;
                height: 0;
            }}
            .stApp {{
                background: radial-gradient(circle at 40% 0%, #0D0D0D 0%, var(--ec-bg) 36%);
                color: var(--ec-text);
                font-family: "Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
            }}
            .main > div {{
                padding-top: 1.0rem;
                padding-left: 1.6rem;
                padding-right: 1.6rem;
            }}
            h1, h2, h3, h4, h5, h6, p, li, label, div, span {{
                color: var(--ec-text);
                font-family: "Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
                box-sizing: border-box;
            }}
            [data-testid="stSidebar"] {{
                background: linear-gradient(180deg, var(--ec-sidebar-bg) 0%, #070707 100%);
                border-right: 1px solid var(--ec-border);
            }}
            [data-testid="stSidebarNav"] {{
                display: none;
            }}
            [data-testid="stSidebarNav"] a {{
                color: var(--ec-text-secondary);
                border-radius: 12px;
                margin-bottom: 0.25rem;
            }}
            [data-testid="stSidebarNav"] a[aria-current="page"],
            [data-testid="stSidebarNav"] a:hover {{
                background: linear-gradient(135deg, var(--ec-red-dark), #A0151B);
                color: var(--ec-text) !important;
            }}
            [data-testid="stVerticalBlockBorderWrapper"],
            [data-testid="stMetric"] {{
                background: linear-gradient(180deg, #131313 0%, #101010 100%);
                border: 1px solid var(--ec-border);
                border-radius: 16px;
                padding: 0.8rem;
                box-shadow: 0 10px 26px rgba(0,0,0,0.22);
            }}
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] > div,
            div[data-baseweb="textarea"] > div,
            .stDateInput > div > div,
            .stNumberInput > div > div {{
                background: var(--ec-surface);
                color: var(--ec-text);
                border-color: var(--ec-border);
                border-radius: 10px;
            }}
            .stButton > button {{
                border: 1px solid var(--ec-border);
                background: var(--ec-surface-elev);
                color: var(--ec-text);
                border-radius: 12px;
                font-weight: 650;
            }}
            .stButton > button[kind="primary"] {{
                border-color: transparent;
                background: linear-gradient(90deg, #B8151B 0%, var(--ec-red) 75%);
                color: #fff;
            }}
            .stButton > button[kind="primary"]:hover {{
                background: linear-gradient(90deg, #C9181F 0%, var(--ec-red-hover) 85%);
                color: #fff;
            }}
            .ec-metric-card, .ec-command-card, .ec-panel {{
                background: linear-gradient(180deg, #131313 0%, #101010 100%);
                border: 1px solid var(--ec-border);
                border-radius: 16px;
                padding: 0.9rem;
                margin-bottom: 0.7rem;
                box-shadow: 0 10px 26px rgba(0,0,0,0.22);
                overflow: hidden;
                max-width: 100%;
            }}
            .ec-command-card *,
            .ec-metric-card *,
            .ec-panel * {{
                min-width: 0;
                overflow-wrap: anywhere;
            }}
            .ec-caption {{ color: var(--ec-text-muted); font-size: 0.92rem; }}
            .ec-kicker {{ color: var(--ec-text-muted); text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; }}
            .ec-value {{ font-size: 1.9rem; font-weight: 700; margin-top: 0.15rem; }}
            .ec-status-pill {{
                display: inline-block;
                border-radius: 999px;
                border: 1px solid var(--ec-border);
                padding: 0.18rem 0.56rem;
                font-size: 0.75rem;
                font-weight: 600;
                margin-left: 0.35rem;
                text-transform: uppercase;
            }}
            div[data-testid="stAlert"] {{
                background: transparent !important;
                border: 0 !important;
                padding: 0 !important;
                color: var(--ec-text);
            }}
            div[data-testid="stAlert"] > div,
            div[data-testid="stAlertContainer"],
            div[data-baseweb="notification"] {{
                background: linear-gradient(180deg, #131313 0%, #101010 100%) !important;
                border: 1px solid var(--ec-border) !important;
                border-radius: 16px !important;
                color: var(--ec-text) !important;
                box-shadow: 0 10px 26px rgba(0,0,0,0.22);
            }}
            div[data-testid="stAlert"] svg {{
                fill: var(--ec-red) !important;
            }}
            .stDataFrame, .stTable {{
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                overflow: hidden;
            }}
            hr {{
                border-color: var(--ec-border);
                opacity: 0.55;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(label: str, status: str) -> str:
    tokens = get_theme_tokens()
    color = _status_color(tokens, status)
    return (
        f"<span class='ec-status-pill' style='border-color:{color}; color:{color};'>"
        f"{label}</span>"
    )


def metric_card(label: str, value: Any, subtext: str | None = None, status: str | None = None) -> None:
    badge = status_badge(status.upper(), status) if status else ""
    sub = f"<div class='ec-caption'>{subtext}</div>" if subtext else ""
    st.markdown(
        f"""
        <div class='ec-metric-card'>
            <div class='ec-kicker'>{label} {badge}</div>
            <div class='ec-value'>{value}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, caption: str | None = None) -> None:
    cap = f"<div class='ec-caption'>{caption}</div>" if caption else ""
    st.markdown(f"<h3 style='margin-bottom:0.2rem;'>{title}</h3>{cap}", unsafe_allow_html=True)


def command_card(title: str, body: str, status: str | None = None) -> None:
    badge = status_badge(status.upper(), status) if status else ""
    st.markdown(
        f"""
        <div class='ec-command-card'>
            <div><strong>{title}</strong> {badge}</div>
            <div class='ec-caption' style='margin-top:0.35rem;'>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
