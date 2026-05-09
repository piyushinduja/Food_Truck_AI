"""SQLite database and safe migration helpers for El Camino Command."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .timing import estimate_menu_timing, has_placeholder_timing

DB_PATH = Path(__file__).parent.parent / "data" / "foodtruck.db"


@contextmanager
def get_conn():
    """Context-managed connection with row factory and FK enforcement."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


TABLE_SCHEMAS = {
    "menu": """
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            category TEXT,
            description TEXT,
            available INTEGER NOT NULL DEFAULT 1,
            prep_time_minutes REAL NOT NULL DEFAULT 1,
            cook_time_minutes REAL NOT NULL DEFAULT 5,
            image_url TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """,
    "inventory": """
        CREATE TABLE IF NOT EXISTS inventory (
            ingredient TEXT PRIMARY KEY,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            reorder_threshold REAL NOT NULL DEFAULT 0,
            cost_per_unit REAL NOT NULL DEFAULT 0,
            critical_threshold REAL NOT NULL DEFAULT 0,
            expiration_date TEXT,
            supplier_id INTEGER,
            category TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """,
    "recipe": """
        CREATE TABLE IF NOT EXISTS recipe (
            menu_id INTEGER NOT NULL,
            ingredient TEXT NOT NULL,
            qty_per_serving REAL NOT NULL,
            PRIMARY KEY (menu_id, ingredient),
            FOREIGN KEY (menu_id) REFERENCES menu(id),
            FOREIGN KEY (ingredient) REFERENCES inventory(ingredient)
        )
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            customer_name TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            total REAL NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'paid',
            payment_id TEXT,
            source TEXT NOT NULL DEFAULT 'kiosk',
            estimated_ready_at TEXT,
            ready_at TEXT,
            kitchen_started_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """,
    "order_items": """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (menu_id) REFERENCES menu(id)
        )
    """,
    "restock_log": """
        CREATE TABLE IF NOT EXISTS restock_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            cost REAL NOT NULL,
            supplier TEXT NOT NULL DEFAULT 'walmart_mock',
            status TEXT NOT NULL DEFAULT 'placed',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "business_config": """
        CREATE TABLE IF NOT EXISTS business_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """,
    "theme_config": """
        CREATE TABLE IF NOT EXISTS theme_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """,
    "suppliers": """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT,
            website TEXT,
            contact_info TEXT,
            estimated_delivery_time TEXT,
            notes TEXT
        )
    """,
    "kitchen_timeline_steps": """
        CREATE TABLE IF NOT EXISTS kitchen_timeline_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            order_item_id INTEGER,
            item_name TEXT NOT NULL,
            action TEXT NOT NULL,
            start_offset_minutes REAL NOT NULL,
            duration_minutes REAL NOT NULL,
            target_start_time TEXT,
            target_finish_time TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            urgency TEXT NOT NULL DEFAULT 'normal',
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """,
    "purchase_orders": """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            status TEXT NOT NULL DEFAULT 'suggested',
            estimated_total REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            approved_at TEXT,
            received_at TEXT,
            notes TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """,
    "purchase_order_items": """
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            ingredient TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            estimated_cost REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id)
        )
    """,
    "agent_events": """
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            action_label TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """,
    "customer_profiles": """
        CREATE TABLE IF NOT EXISTS customer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            height_cm REAL,
            weight_kg REAL,
            age INTEGER,
            sex TEXT,
            activity_level TEXT,
            goal TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT
        )
    """,
    "customer_macro_targets": """
        CREATE TABLE IF NOT EXISTS customer_macro_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            target_date TEXT NOT NULL,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (customer_id) REFERENCES customer_profiles(id)
        )
    """,
    "menu_nutrition": """
        CREATE TABLE IF NOT EXISTS menu_nutrition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_item_id INTEGER NOT NULL UNIQUE,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            fiber_g REAL DEFAULT 0,
            sugar_g REAL DEFAULT 0,
            sodium_mg REAL DEFAULT 0,
            source TEXT DEFAULT 'seeded_estimate',
            updated_at TEXT,
            FOREIGN KEY (menu_item_id) REFERENCES menu(id)
        )
    """,
    "order_macro_logs": """
        CREATE TABLE IF NOT EXISTS order_macro_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            order_id INTEGER,
            log_date TEXT NOT NULL,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'order',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (customer_id) REFERENCES customer_profiles(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """,
    "daily_macro_summaries": """
        CREATE TABLE IF NOT EXISTS daily_macro_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            summary_date TEXT NOT NULL,
            calories_target REAL,
            protein_target_g REAL,
            carbs_target_g REAL,
            fat_target_g REAL,
            calories_consumed REAL,
            protein_consumed_g REAL,
            carbs_consumed_g REAL,
            fat_consumed_g REAL,
            calories_remaining REAL,
            protein_remaining_g REAL,
            carbs_remaining_g REAL,
            fat_remaining_g REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT,
            FOREIGN KEY (customer_id) REFERENCES customer_profiles(id)
        )
    """,
    "macro_ai_suggestions": """
        CREATE TABLE IF NOT EXISTS macro_ai_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            suggestion_date TEXT NOT NULL,
            context TEXT NOT NULL,
            suggestion TEXT NOT NULL,
            recommended_items_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
}


MIGRATION_COLUMNS = {
    "menu": [
        "prep_time_minutes REAL NOT NULL DEFAULT 1",
        "cook_time_minutes REAL NOT NULL DEFAULT 5",
        "image_url TEXT",
        "sort_order INTEGER NOT NULL DEFAULT 0",
    ],
    "inventory": [
        "critical_threshold REAL NOT NULL DEFAULT 0",
        "expiration_date TEXT",
        "supplier_id INTEGER",
        "category TEXT",
    ],
    "orders": [
        "order_number TEXT",
        "source TEXT NOT NULL DEFAULT 'kiosk'",
        "estimated_ready_at TEXT",
        "ready_at TEXT",
        "kitchen_started_at TEXT",
    ],
}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column_def: str) -> None:
    col_name = column_def.split()[0].strip()
    cols = _table_columns(conn, table)
    if col_name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def migrate_db() -> None:
    """Safe, idempotent schema migration for existing DB files."""
    with get_conn() as conn:
        for ddl in TABLE_SCHEMAS.values():
            conn.execute(ddl)

        for table, column_defs in MIGRATION_COLUMNS.items():
            if not _table_exists(conn, table):
                continue
            for column_def in column_defs:
                _add_column_if_missing(conn, table, column_def)

        # Backfill sensible defaults for older rows.
        conn.execute(
            """
            UPDATE orders
            SET order_number = 'EC-' || printf('%04d', id)
            WHERE order_number IS NULL OR TRIM(order_number) = ''
            """
        )
        conn.execute(
            "UPDATE orders SET source = 'kiosk' WHERE source IS NULL OR TRIM(source) = ''"
        )
        conn.execute(
            """
            UPDATE menu
            SET prep_time_minutes = COALESCE(prep_time_minutes, 1),
                cook_time_minutes = COALESCE(cook_time_minutes, 5)
            """
        )
        menu_rows = conn.execute(
            """
            SELECT id, name, category, description, prep_time_minutes, cook_time_minutes
            FROM menu
            """
        ).fetchall()
        for row in menu_rows:
            item = dict(row)
            if not has_placeholder_timing(item):
                continue
            ingredient_rows = conn.execute(
                "SELECT ingredient FROM recipe WHERE menu_id = ?",
                (item["id"],),
            ).fetchall()
            ingredients = [ingredient["ingredient"] for ingredient in ingredient_rows]
            prep, cook = estimate_menu_timing(item, ingredients)
            conn.execute(
                """
                UPDATE menu
                SET prep_time_minutes = ?, cook_time_minutes = ?
                WHERE id = ?
                """,
                (prep, cook, item["id"]),
            )
        conn.execute(
            """
            UPDATE inventory
            SET critical_threshold = CASE
                WHEN critical_threshold IS NULL OR critical_threshold = 0
                THEN ROUND(reorder_threshold * 0.5, 2)
                ELSE critical_threshold
            END
            """
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kitchen_timeline_order_id ON kitchen_timeline_steps(order_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_events_resolved ON agent_events(resolved, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_profiles_lookup ON customer_profiles(customer_name, phone)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_macro_targets_date ON customer_macro_targets(customer_id, target_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_order_macro_logs_customer_date ON order_macro_logs(customer_id, log_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_order_macro_logs_order ON order_macro_logs(order_id)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_macro_summaries_date ON daily_macro_summaries(customer_id, summary_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_macro_ai_suggestions_customer_date ON macro_ai_suggestions(customer_id, suggestion_date)"
        )


def init_db() -> None:
    """Initialize database and run safe migrations."""
    migrate_db()


def reset_db() -> None:
    """Drop all application tables and recreate schema."""
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = OFF;
            DROP TABLE IF EXISTS kitchen_timeline_steps;
            DROP TABLE IF EXISTS purchase_order_items;
            DROP TABLE IF EXISTS purchase_orders;
            DROP TABLE IF EXISTS agent_events;
            DROP TABLE IF EXISTS macro_ai_suggestions;
            DROP TABLE IF EXISTS daily_macro_summaries;
            DROP TABLE IF EXISTS order_macro_logs;
            DROP TABLE IF EXISTS customer_macro_targets;
            DROP TABLE IF EXISTS customer_profiles;
            DROP TABLE IF EXISTS menu_nutrition;
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS recipe;
            DROP TABLE IF EXISTS inventory;
            DROP TABLE IF EXISTS menu;
            DROP TABLE IF EXISTS suppliers;
            DROP TABLE IF EXISTS business_config;
            DROP TABLE IF EXISTS theme_config;
            DROP TABLE IF EXISTS restock_log;
            PRAGMA foreign_keys = ON;
            """
        )
    migrate_db()
