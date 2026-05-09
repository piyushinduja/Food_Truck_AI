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
    "macroActivityMultipliers": {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    },
    "macroGoalAdjustments": {
        "lose weight": -0.15,
        "maintain": 0.0,
        "gain muscle": 0.10,
        "high protein": 0.0,
        "custom macros": 0.0,
    },
    "macroProteinPerKg": {
        "lose weight": 1.8,
        "maintain": 1.6,
        "gain muscle": 2.0,
        "high protein": 2.2,
        "custom macros": 1.6,
    },
    "macroFatPercent": {
        "lose weight": 0.25,
        "maintain": 0.28,
        "gain muscle": 0.25,
        "high protein": 0.24,
        "custom macros": 0.28,
    },
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
