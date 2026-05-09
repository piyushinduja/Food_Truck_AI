"""Customer profile, macro target, intake, and summary logic."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import config, nutrition, orders as orders_mod
from .autopilot import log_agent_event
from .db import get_conn, init_db


def _today() -> str:
    return date.today().isoformat()


def create_customer_profile(
    customer_name: str,
    phone: str | None = None,
    email: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    age: int | None = None,
    sex: str | None = None,
    activity_level: str | None = None,
    goal: str | None = None,
) -> dict:
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO customer_profiles (
                customer_name, phone, email, height_cm, weight_kg, age,
                sex, activity_level, goal, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                customer_name.strip(),
                phone or None,
                email or None,
                height_cm,
                weight_kg,
                age,
                sex,
                activity_level,
                goal,
            ),
        )
        customer_id = cur.lastrowid
    log_agent_event("Customer Macro Agent", "healthy", "Macro profile created", f"Profile created for {customer_name}.", "Profile")
    return get_customer_profile(customer_id) or {"id": customer_id}


def update_customer_profile(customer_id: int, **updates: Any) -> dict:
    allowed = {
        "customer_name",
        "phone",
        "email",
        "height_cm",
        "weight_kg",
        "age",
        "sex",
        "activity_level",
        "goal",
    }
    payload = {key: value for key, value in updates.items() if key in allowed}
    if not payload:
        return {"ok": False, "error": "no_valid_fields"}
    sets = ", ".join(f"{key} = ?" for key in payload)
    values = list(payload.values()) + [customer_id]
    init_db()
    with get_conn() as conn:
        conn.execute(
            f"UPDATE customer_profiles SET {sets}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
    return {"ok": True, "customer_id": customer_id}


def get_customer_profile(customer_id: int) -> dict | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customer_profiles WHERE id = ?", (customer_id,)).fetchone()
    return dict(row) if row else None


def list_customer_profiles() -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM customer_profiles ORDER BY datetime(updated_at) DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def find_or_create_customer_by_name_phone(customer_name: str, phone: str | None = None, **profile_fields: Any) -> dict:
    name = customer_name.strip() or "Guest"
    init_db()
    with get_conn() as conn:
        if phone:
            row = conn.execute(
                "SELECT * FROM customer_profiles WHERE phone = ? ORDER BY id DESC LIMIT 1",
                (phone,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM customer_profiles WHERE lower(customer_name) = lower(?) ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
    if row:
        profile = dict(row)
        if profile_fields:
            update_customer_profile(profile["id"], customer_name=name, phone=phone or profile.get("phone"), **profile_fields)
            profile = get_customer_profile(profile["id"]) or profile
        return profile
    return create_customer_profile(customer_name=name, phone=phone, **profile_fields)


def calculate_macro_targets(profile: dict) -> dict:
    weight_kg = float(profile.get("weight_kg") or 0)
    height_cm = float(profile.get("height_cm") or 0)
    age = int(profile.get("age") or 0)
    sex = str(profile.get("sex") or "unspecified").lower()
    goal = str(profile.get("goal") or "maintain").lower()
    activity = str(profile.get("activity_level") or "moderate").lower()

    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("height_cm, weight_kg, and age are required for macro calculation")

    sex_adjustment = 5 if sex in {"male", "m"} else -161 if sex in {"female", "f"} else -78
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + sex_adjustment

    cfg = config.get_business_config()
    activity_multipliers = dict(cfg.get("macroActivityMultipliers") or {})
    goal_adjustments = dict(cfg.get("macroGoalAdjustments") or {})
    protein_per_kg = dict(cfg.get("macroProteinPerKg") or {})
    fat_percent = dict(cfg.get("macroFatPercent") or {})

    tdee = bmr * float(activity_multipliers.get(activity, activity_multipliers.get("moderate", 1.55)))
    calories = max(1200.0, tdee * (1 + float(goal_adjustments.get(goal, 0))))
    protein_g = max(0.0, weight_kg * float(protein_per_kg.get(goal, protein_per_kg.get("maintain", 1.6))))
    fat_g = max(0.0, (calories * float(fat_percent.get(goal, fat_percent.get("maintain", 0.28)))) / 9)
    carb_calories = max(0.0, calories - (protein_g * 4) - (fat_g * 9))
    carbs_g = carb_calories / 4

    return {
        "calories": round(calories),
        "protein_g": round(protein_g),
        "carbs_g": round(carbs_g),
        "fat_g": round(fat_g),
        "bmr": round(bmr),
        "tdee": round(tdee),
        "source": "mifflin_st_jeor",
    }


def save_macro_targets(customer_id: int, target_date: str, targets: dict) -> dict:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO customer_macro_targets (
                customer_id, target_date, calories, protein_g, carbs_g, fat_g, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id, target_date) DO UPDATE SET
                calories = excluded.calories,
                protein_g = excluded.protein_g,
                carbs_g = excluded.carbs_g,
                fat_g = excluded.fat_g,
                source = excluded.source,
                created_at = datetime('now')
            """,
            (
                customer_id,
                target_date,
                float(targets["calories"]),
                float(targets["protein_g"]),
                float(targets["carbs_g"]),
                float(targets["fat_g"]),
                str(targets.get("source") or "macro_calculator"),
            ),
        )
    recalculate_daily_macro_summary(customer_id, target_date)
    log_agent_event("Customer Macro Agent", "healthy", "Macro target calculated", f"Targets saved for customer #{customer_id}.", "Macro Goals")
    return {"ok": True, "customer_id": customer_id, "target_date": target_date}


def get_macro_targets(customer_id: int, target_date: str) -> dict | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM customer_macro_targets
            WHERE customer_id = ? AND target_date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (customer_id, target_date),
        ).fetchone()
    return dict(row) if row else None


def log_order_macros(customer_id: int, order_id: int) -> dict:
    order = orders_mod.get_order(order_id)
    if not order:
        return {"ok": False, "error": "order_not_found"}
    totals = nutrition.estimate_order_nutrition(order.get("items", []))
    log_date = str(order.get("created_at") or _today()).split(" ")[0]
    init_db()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM order_macro_logs WHERE customer_id = ? AND order_id = ?",
            (customer_id, order_id),
        ).fetchone()
        if existing:
            return {"ok": True, "already_logged": True, "order_id": order_id}
        conn.execute(
            """
            INSERT INTO order_macro_logs (
                customer_id, order_id, log_date, calories, protein_g, carbs_g, fat_g, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'order')
            """,
            (
                customer_id,
                order_id,
                log_date,
                totals["calories"],
                totals["protein_g"],
                totals["carbs_g"],
                totals["fat_g"],
            ),
        )
    recalculate_daily_macro_summary(customer_id, log_date)
    log_agent_event("Customer Macro Agent", "healthy", "Order macro logged", f"Order #{order_id} added to customer #{customer_id} macro log.", "Macro Log")
    return {"ok": True, "order_id": order_id, "nutrition": totals}


def recalculate_daily_macro_summary(customer_id: int, summary_date: str) -> dict:
    targets = get_macro_targets(customer_id, summary_date)
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(calories), 0) AS calories,
                COALESCE(SUM(protein_g), 0) AS protein_g,
                COALESCE(SUM(carbs_g), 0) AS carbs_g,
                COALESCE(SUM(fat_g), 0) AS fat_g
            FROM order_macro_logs
            WHERE customer_id = ? AND log_date = ?
            """,
            (customer_id, summary_date),
        ).fetchone()
        consumed = dict(row)

        target_values = {
            "calories": float(targets["calories"]) if targets else 0.0,
            "protein_g": float(targets["protein_g"]) if targets else 0.0,
            "carbs_g": float(targets["carbs_g"]) if targets else 0.0,
            "fat_g": float(targets["fat_g"]) if targets else 0.0,
        }
        remaining = {
            key: round(float(target_values[key]) - float(consumed[key]), 2)
            for key in target_values
        }

        conn.execute(
            """
            INSERT INTO daily_macro_summaries (
                customer_id, summary_date,
                calories_target, protein_target_g, carbs_target_g, fat_target_g,
                calories_consumed, protein_consumed_g, carbs_consumed_g, fat_consumed_g,
                calories_remaining, protein_remaining_g, carbs_remaining_g, fat_remaining_g,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(customer_id, summary_date) DO UPDATE SET
                calories_target = excluded.calories_target,
                protein_target_g = excluded.protein_target_g,
                carbs_target_g = excluded.carbs_target_g,
                fat_target_g = excluded.fat_target_g,
                calories_consumed = excluded.calories_consumed,
                protein_consumed_g = excluded.protein_consumed_g,
                carbs_consumed_g = excluded.carbs_consumed_g,
                fat_consumed_g = excluded.fat_consumed_g,
                calories_remaining = excluded.calories_remaining,
                protein_remaining_g = excluded.protein_remaining_g,
                carbs_remaining_g = excluded.carbs_remaining_g,
                fat_remaining_g = excluded.fat_remaining_g,
                updated_at = excluded.updated_at
            """,
            (
                customer_id,
                summary_date,
                target_values["calories"],
                target_values["protein_g"],
                target_values["carbs_g"],
                target_values["fat_g"],
                consumed["calories"],
                consumed["protein_g"],
                consumed["carbs_g"],
                consumed["fat_g"],
                remaining["calories"],
                remaining["protein_g"],
                remaining["carbs_g"],
                remaining["fat_g"],
            ),
        )
    return get_daily_macro_summary(customer_id, summary_date)


def get_daily_macro_summary(customer_id: int, summary_date: str) -> dict:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM daily_macro_summaries
            WHERE customer_id = ? AND summary_date = ?
            """,
            (customer_id, summary_date),
        ).fetchone()
    if not row:
        return recalculate_daily_macro_summary(customer_id, summary_date)
    return dict(row)


def get_macro_history(customer_id: int, days: int = 7) -> list[dict]:
    start = date.today() - timedelta(days=max(1, days) - 1)
    result = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        result.append(get_daily_macro_summary(customer_id, day))
    return result


def get_recent_macro_orders(customer_id: int, days: int = 7) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT oml.*, o.order_number, o.customer_name, o.total
            FROM order_macro_logs oml
            LEFT JOIN orders o ON o.id = oml.order_id
            WHERE oml.customer_id = ? AND oml.log_date >= ?
            ORDER BY oml.log_date DESC, oml.id DESC
            """,
            (customer_id, since),
        ).fetchall()
    return [dict(row) for row in rows]


def macro_customer_count() -> int:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM customer_profiles").fetchone()
    return int(row["c"] if row else 0)


def macro_agent_activity_today() -> dict:
    today = _today()
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT title, COUNT(*) AS c
            FROM agent_events
            WHERE agent_name = 'Customer Macro Agent'
              AND date(created_at) = ?
            GROUP BY title
            """,
            (today,),
        ).fetchall()
    return {row["title"]: int(row["c"]) for row in rows}
