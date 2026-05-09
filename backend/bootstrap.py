"""Startup helpers for app pages."""
from __future__ import annotations

from .db import get_conn, init_db
from .seed import seed


def ensure_app_ready() -> None:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM menu").fetchone()
    if not row or int(row["c"]) == 0:
        seed()
        return

    with get_conn() as conn:
        nutrition_row = conn.execute("SELECT COUNT(*) AS c FROM menu_nutrition").fetchone()
    if not nutrition_row or int(nutrition_row["c"]) == 0:
        seed()
