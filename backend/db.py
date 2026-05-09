"""SQLite database for the food truck app.

Single file at data/foodtruck.db. Schema covers menu, ingredients,
inventory, orders, order items, and restock log.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

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


SCHEMA = """
CREATE TABLE IF NOT EXISTS menu (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    price REAL NOT NULL,
    category TEXT,
    description TEXT,
    available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS inventory (
    ingredient TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    reorder_threshold REAL NOT NULL DEFAULT 0,
    cost_per_unit REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipe (
    menu_id INTEGER NOT NULL,
    ingredient TEXT NOT NULL,
    qty_per_serving REAL NOT NULL,
    PRIMARY KEY (menu_id, ingredient),
    FOREIGN KEY (menu_id) REFERENCES menu(id),
    FOREIGN KEY (ingredient) REFERENCES inventory(ingredient)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, preparing, ready, completed
    total REAL NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'paid',
    payment_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    notes TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (menu_id) REFERENCES menu(id)
);

CREATE TABLE IF NOT EXISTS restock_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    cost REAL NOT NULL,
    supplier TEXT NOT NULL DEFAULT 'walmart_mock',
    status TEXT NOT NULL DEFAULT 'placed',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db():
    """Create tables if they don't exist. Also runs lightweight migrations."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Migration: add phone column to existing DBs
        cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
        if "phone" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN phone TEXT")


def reset_db():
    """Drop everything and recreate. Useful for demos."""
    with get_conn() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS recipe;
            DROP TABLE IF EXISTS inventory;
            DROP TABLE IF EXISTS menu;
            DROP TABLE IF EXISTS restock_log;
        """)
        conn.executescript(SCHEMA)
