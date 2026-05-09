"""Business and app configuration helpers backed by SQLite."""
from __future__ import annotations

import json
from typing import Any

from .db import get_conn, init_db


DEFAULT_BUSINESS_CONFIG: dict[str, Any] = {
    "businessName": "El Camino Command",
    "tagline": "Run the truck. Watch the numbers. Serve food on time.",
    "taxRate": 0.0825,
    "currency": "USD",
    "openStatus": "open",
    "truckLocation": "Downtown Austin - Congress Ave",
    "defaultPrepBufferMinutes": 2,
    "expiryWarningDays": 3,
    "requireHumanApprovalForPurchasing": True,
}


def _serialize(value: Any) -> str:
    if isinstance(value, (dict, list, bool, int, float)):
        return json.dumps(value)
    if value is None:
        return ""
    return str(value)


def _deserialize(raw: str, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(default, (dict, list, bool, int, float)):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        if isinstance(default, bool):
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "open"}
        if isinstance(default, int) and not isinstance(default, bool):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        return value
    return raw


def get_config(key: str, default: Any = None) -> Any:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM business_config WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return default
    return _deserialize(row["value"], default)


def set_config(key: str, value: Any) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO business_config (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, _serialize(value)),
        )


def get_business_config() -> dict[str, Any]:
    init_db()
    config = dict(DEFAULT_BUSINESS_CONFIG)
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM business_config").fetchall()

    for row in rows:
        key = row["key"]
        default = config.get(key)
        config[key] = _deserialize(row["value"], default)

    # Ensure required keys exist in DB for editability.
    for key, value in DEFAULT_BUSINESS_CONFIG.items():
        if key not in {r["key"] for r in rows}:
            set_config(key, value)
    return config


def update_business_config(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in data.items():
        set_config(key, value)
    return get_business_config()
