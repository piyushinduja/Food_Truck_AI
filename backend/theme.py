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
                --ec-surface: {tokens['surface']};
                --ec-surface-elev: {tokens['surface_elevated']};
                --ec-text: {tokens['text_primary']};
                --ec-text-muted: {tokens['text_secondary']};
                --ec-border: {tokens['border']};
                --ec-red: {tokens['primary_red']};
                --ec-danger: {tokens['danger_red']};
                --ec-warning: {tokens['warning']};
                --ec-success: {tokens['success']};
            }}
            .stApp {{
                background: var(--ec-bg);
                color: var(--ec-text);
            }}
            .main > div {{
                padding-top: 1rem;
            }}
            h1, h2, h3, h4, h5, h6, p, li, label, div {{
                color: var(--ec-text);
            }}
            [data-testid="stSidebar"] {{
                background: var(--ec-surface);
                border-right: 1px solid var(--ec-border);
            }}
            [data-testid="stMetric"] {{
                background: var(--ec-surface);
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                padding: 0.8rem;
            }}
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] > div,
            div[data-baseweb="textarea"] > div,
            .stDateInput > div > div,
            .stNumberInput > div > div {{
                background: var(--ec-surface);
                color: var(--ec-text);
                border-color: var(--ec-border);
            }}
            .stButton > button {{
                border: 1px solid var(--ec-border);
                background: var(--ec-surface-elev);
                color: var(--ec-text);
                border-radius: 10px;
            }}
            .stButton > button[kind="primary"] {{
                border-color: var(--ec-red);
                background: var(--ec-red);
                color: #fff;
            }}
            .ec-metric-card, .ec-command-card, .ec-panel {{
                background: var(--ec-surface);
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                padding: 0.9rem;
                margin-bottom: 0.7rem;
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
            }}
            .stDataFrame, .stTable {{
                border: 1px solid var(--ec-border);
                border-radius: 12px;
                overflow: hidden;
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
