"""Startup helpers for app pages."""
from __future__ import annotations

import os
from pathlib import Path

from .db import get_conn, init_db
from .seed import seed

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load variables from a .env file in the project root without requiring python-dotenv."""
    env_file = _PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def ensure_app_ready() -> None:
    _load_dotenv()
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
