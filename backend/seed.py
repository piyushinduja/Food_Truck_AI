"""Seed the database with realistic El Camino Command demo data."""
from __future__ import annotations

from datetime import date, timedelta

from . import config as config_mod
from . import menu as menu_mod
from .db import get_conn, init_db
from .theme_tokens import DEFAULT_THEME_TOKENS


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


SUPPLIERS = [
    {
        "name": "Walmart Mock",
        "type": "retail",
        "website": "https://example.com/walmart-mock",
        "contact_info": "walmart-mock@example.com",
        "estimated_delivery_time": "Same day",
        "notes": "General emergency restock",
    },
    {
        "name": "Costco Mock",
        "type": "wholesale",
        "website": "https://example.com/costco-mock",
        "contact_info": "costco-mock@example.com",
        "estimated_delivery_time": "Next day",
        "notes": "Bulk packaged goods",
    },
    {
        "name": "Restaurant Depot Mock",
        "type": "foodservice",
        "website": "https://example.com/rd-mock",
        "contact_info": "rd-mock@example.com",
        "estimated_delivery_time": "Next morning",
        "notes": "Protein and produce",
    },
    {
        "name": "Local Supplier Mock",
        "type": "local",
        "website": "https://example.com/local-supplier-mock",
        "contact_info": "local-mock@example.com",
        "estimated_delivery_time": "2-4 hours",
        "notes": "Fresh herbs and produce",
    },
]


MENU = [
    {
        "name": "Carne Asada Taco",
        "price": 3.50,
        "category": "tacos",
        "description": "Grilled steak, onion, cilantro on corn tortilla",
        "prep_time_minutes": 1.2,
        "cook_time_minutes": 3.8,
        "image_url": "https://unsplash.com/photos/_j4S4V2C8ew/download?force=true",
        "sort_order": 10,
    },
    {
        "name": "Al Pastor Taco",
        "price": 3.50,
        "category": "tacos",
        "description": "Marinated pork with pineapple",
        "prep_time_minutes": 1.1,
        "cook_time_minutes": 3.4,
        "image_url": "https://unsplash.com/photos/wIqpmuOloVA/download?force=true",
        "sort_order": 20,
    },
    {
        "name": "Veggie Taco",
        "price": 3.00,
        "category": "tacos",
        "description": "Black beans, peppers, queso fresco",
        "prep_time_minutes": 1.0,
        "cook_time_minutes": 3.1,
        "image_url": "https://unsplash.com/photos/lP5MCM6nZ5A/download?force=true",
        "sort_order": 30,
    },
    {
        "name": "Carne Burrito",
        "price": 9.50,
        "category": "burritos",
        "description": "Steak, rice, beans, salsa, cheese",
        "prep_time_minutes": 2.4,
        "cook_time_minutes": 6.8,
        "image_url": "https://unsplash.com/photos/p-O37cSAV_4/download?force=true",
        "sort_order": 40,
    },
    {
        "name": "Veggie Burrito",
        "price": 8.50,
        "category": "burritos",
        "description": "Beans, rice, peppers, queso fresco, salsa",
        "prep_time_minutes": 2.2,
        "cook_time_minutes": 6.2,
        "image_url": "https://unsplash.com/photos/qYtfN2109Wg/download?force=true",
        "sort_order": 50,
    },
    {
        "name": "Chips & Guacamole",
        "price": 5.00,
        "category": "sides",
        "description": "Fresh tortilla chips with house guacamole",
        "prep_time_minutes": 1.6,
        "cook_time_minutes": 2.3,
        "image_url": "https://images.pexels.com/photos/7601338/pexels-photo-7601338.jpeg?auto=compress&cs=tinysrgb&w=1100",
        "sort_order": 60,
    },
    {
        "name": "Loaded Nachos",
        "price": 8.00,
        "category": "sides",
        "description": "Chips, beans, cheese, salsa, jalapeños",
        "prep_time_minutes": 1.8,
        "cook_time_minutes": 4.8,
        "image_url": "https://images.pexels.com/photos/27603312/pexels-photo-27603312.jpeg?auto=compress&cs=tinysrgb&w=1100",
        "sort_order": 70,
    },
    {
        "name": "Coke",
        "price": 2.50,
        "category": "drinks",
        "description": "12 oz can",
        "prep_time_minutes": 0.2,
        "cook_time_minutes": 0.2,
        "image_url": "https://images.pexels.com/photos/14650671/pexels-photo-14650671.jpeg?auto=compress&cs=tinysrgb&w=1100",
        "sort_order": 80,
    },
    {
        "name": "Lemonade",
        "price": 3.00,
        "category": "drinks",
        "description": "Fresh-squeezed",
        "prep_time_minutes": 0.4,
        "cook_time_minutes": 0.2,
        "image_url": "https://images.pexels.com/photos/2109099/pexels-photo-2109099.jpeg?auto=compress&cs=tinysrgb&w=1100",
        "sort_order": 90,
    },
    {
        "name": "Horchata",
        "price": 3.50,
        "category": "drinks",
        "description": "Cinnamon rice milk",
        "prep_time_minutes": 0.6,
        "cook_time_minutes": 0.2,
        "image_url": "https://images.pexels.com/photos/5946963/pexels-photo-5946963.jpeg?auto=compress&cs=tinysrgb&w=1100",
        "sort_order": 100,
    },
]


# ingredient, qty, unit, reorder_threshold, critical_threshold, cost, category, supplier_name, expiration
INVENTORY = [
    ("corn_tortilla", 1000, "pcs", 100, 40, 0.10, "dry", "Costco Mock", _d(45)),
    ("flour_tortilla", 300, "pcs", 50, 20, 0.30, "dry", "Costco Mock", _d(45)),
    ("steak", 20000, "g", 3000, 1200, 0.025, "protein", "Restaurant Depot Mock", _d(4)),
    ("pork", 15000, "g", 2500, 1000, 0.020, "protein", "Restaurant Depot Mock", _d(3)),
    ("black_beans", 15000, "g", 2000, 800, 0.005, "dry", "Costco Mock", _d(120)),
    ("rice", 12000, "g", 2000, 800, 0.003, "dry", "Costco Mock", _d(120)),
    ("cheese", 8000, "g", 1500, 500, 0.012, "dairy", "Restaurant Depot Mock", _d(7)),
    ("queso_fresco", 6000, "g", 1000, 350, 0.018, "dairy", "Restaurant Depot Mock", _d(6)),
    ("onion", 8000, "g", 1500, 500, 0.003, "produce", "Local Supplier Mock", _d(2)),
    ("cilantro", 2000, "g", 400, 150, 0.020, "produce", "Local Supplier Mock", _d(1)),
    ("pineapple", 5000, "g", 1000, 300, 0.005, "produce", "Local Supplier Mock", _d(3)),
    ("avocado", 100, "pcs", 20, 8, 1.20, "produce", "Local Supplier Mock", _d(2)),
    ("bell_peppers", 5000, "g", 1000, 300, 0.006, "produce", "Local Supplier Mock", _d(4)),
    ("jalapeno", 2000, "g", 400, 140, 0.008, "produce", "Local Supplier Mock", _d(5)),
    ("salsa", 8000, "g", 1500, 500, 0.005, "prepared", "Restaurant Depot Mock", _d(14)),
    ("tortilla_chips", 12000, "g", 2500, 1000, 0.008, "dry", "Costco Mock", _d(90)),
    ("lime", 150, "pcs", 30, 10, 0.25, "produce", "Local Supplier Mock", _d(5)),
    ("coke_can", 200, "pcs", 40, 15, 0.60, "beverage", "Walmart Mock", _d(180)),
    ("lemon", 100, "pcs", 20, 8, 0.40, "produce", "Local Supplier Mock", _d(4)),
    ("rice_milk", 12000, "ml", 2500, 1000, 0.004, "beverage", "Walmart Mock", _d(40)),
    ("cinnamon", 500, "g", 100, 40, 0.030, "dry", "Costco Mock", _d(365)),
    ("sugar", 5000, "g", 1000, 350, 0.002, "dry", "Costco Mock", _d(365)),
]


RECIPES = {
    "Carne Asada Taco": [
        ("corn_tortilla", 1),
        ("steak", 60),
        ("onion", 15),
        ("cilantro", 3),
        ("lime", 0.1),
    ],
    "Al Pastor Taco": [
        ("corn_tortilla", 1),
        ("pork", 60),
        ("pineapple", 20),
        ("onion", 10),
        ("cilantro", 3),
    ],
    "Veggie Taco": [
        ("corn_tortilla", 1),
        ("black_beans", 40),
        ("bell_peppers", 30),
        ("queso_fresco", 20),
    ],
    "Carne Burrito": [
        ("flour_tortilla", 1),
        ("steak", 100),
        ("rice", 80),
        ("black_beans", 60),
        ("salsa", 30),
        ("cheese", 30),
    ],
    "Veggie Burrito": [
        ("flour_tortilla", 1),
        ("black_beans", 100),
        ("rice", 80),
        ("bell_peppers", 50),
        ("queso_fresco", 30),
        ("salsa", 30),
    ],
    "Chips & Guacamole": [
        ("tortilla_chips", 80),
        ("avocado", 1),
        ("onion", 10),
        ("lime", 0.25),
        ("cilantro", 2),
    ],
    "Loaded Nachos": [
        ("tortilla_chips", 120),
        ("black_beans", 60),
        ("cheese", 50),
        ("salsa", 40),
        ("jalapeno", 15),
    ],
    "Coke": [("coke_can", 1)],
    "Lemonade": [("lemon", 1), ("sugar", 20)],
    "Horchata": [("rice_milk", 350), ("cinnamon", 2), ("sugar", 15)],
}

MENU_NUTRITION = {
    "Carne Asada Taco": {"calories": 210, "protein_g": 15, "carbs_g": 21, "fat_g": 8, "fiber_g": 3, "sugar_g": 2, "sodium_mg": 430},
    "Al Pastor Taco": {"calories": 230, "protein_g": 14, "carbs_g": 23, "fat_g": 9, "fiber_g": 2, "sugar_g": 4, "sodium_mg": 470},
    "Veggie Taco": {"calories": 190, "protein_g": 8, "carbs_g": 25, "fat_g": 7, "fiber_g": 6, "sugar_g": 3, "sodium_mg": 360},
    "Carne Burrito": {"calories": 760, "protein_g": 38, "carbs_g": 82, "fat_g": 30, "fiber_g": 11, "sugar_g": 5, "sodium_mg": 1260},
    "Veggie Burrito": {"calories": 650, "protein_g": 24, "carbs_g": 88, "fat_g": 22, "fiber_g": 15, "sugar_g": 6, "sodium_mg": 980},
    "Chips & Guacamole": {"calories": 440, "protein_g": 7, "carbs_g": 42, "fat_g": 28, "fiber_g": 9, "sugar_g": 3, "sodium_mg": 520},
    "Loaded Nachos": {"calories": 820, "protein_g": 24, "carbs_g": 78, "fat_g": 46, "fiber_g": 12, "sugar_g": 5, "sodium_mg": 1420},
    "Coke": {"calories": 140, "protein_g": 0, "carbs_g": 39, "fat_g": 0, "fiber_g": 0, "sugar_g": 39, "sodium_mg": 45},
    "Lemonade": {"calories": 160, "protein_g": 0, "carbs_g": 41, "fat_g": 0, "fiber_g": 0, "sugar_g": 38, "sodium_mg": 20},
    "Horchata": {"calories": 230, "protein_g": 3, "carbs_g": 48, "fat_g": 4, "fiber_g": 1, "sugar_g": 32, "sodium_mg": 85},
}


def seed() -> None:
    init_db()
    with get_conn() as conn:
        for s in SUPPLIERS:
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
                (
                    s["name"],
                    s["type"],
                    s["website"],
                    s["contact_info"],
                    s["estimated_delivery_time"],
                    s["notes"],
                ),
            )

        supplier_lookup = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM suppliers").fetchall()
        }

        for m in MENU:
            conn.execute(
                """
                INSERT INTO menu
                (name, price, category, description, available, prep_time_minutes, cook_time_minutes, image_url, sort_order)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    price = excluded.price,
                    category = excluded.category,
                    description = excluded.description,
                    prep_time_minutes = excluded.prep_time_minutes,
                    cook_time_minutes = excluded.cook_time_minutes,
                    image_url = excluded.image_url,
                    sort_order = excluded.sort_order
                """,
                (
                    m["name"],
                    m["price"],
                    m["category"],
                    m["description"],
                    m["prep_time_minutes"],
                    m["cook_time_minutes"],
                    m["image_url"],
                    m["sort_order"],
                ),
            )

        for ingredient, qty, unit, reorder, critical, cost, category, supplier_name, expiry in INVENTORY:
            supplier_id = supplier_lookup.get(supplier_name)
            conn.execute(
                """
                INSERT INTO inventory
                (ingredient, quantity, unit, reorder_threshold, cost_per_unit, critical_threshold, expiration_date, supplier_id, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ingredient) DO UPDATE SET
                    quantity = excluded.quantity,
                    unit = excluded.unit,
                    reorder_threshold = excluded.reorder_threshold,
                    cost_per_unit = excluded.cost_per_unit,
                    critical_threshold = excluded.critical_threshold,
                    expiration_date = excluded.expiration_date,
                    supplier_id = excluded.supplier_id,
                    category = excluded.category
                """,
                (
                    ingredient,
                    qty,
                    unit,
                    reorder,
                    cost,
                    critical,
                    expiry,
                    supplier_id,
                    category,
                ),
            )

        name_to_id = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM menu").fetchall()
        }

        for menu_name, recipe_items in RECIPES.items():
            menu_id = name_to_id[menu_name]
            for ingredient, qty in recipe_items:
                conn.execute(
                    """
                    INSERT INTO recipe (menu_id, ingredient, qty_per_serving)
                    VALUES (?, ?, ?)
                    ON CONFLICT(menu_id, ingredient) DO UPDATE SET
                        qty_per_serving = excluded.qty_per_serving
                    """,
                    (menu_id, ingredient, qty),
                )

        for menu_name, nutrition in MENU_NUTRITION.items():
            menu_id = name_to_id[menu_name]
            conn.execute(
                """
                INSERT INTO menu_nutrition (
                    menu_item_id, calories, protein_g, carbs_g, fat_g,
                    fiber_g, sugar_g, sodium_mg, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'seeded_estimate', datetime('now'))
                ON CONFLICT(menu_item_id) DO UPDATE SET
                    calories = excluded.calories,
                    protein_g = excluded.protein_g,
                    carbs_g = excluded.carbs_g,
                    fat_g = excluded.fat_g,
                    fiber_g = excluded.fiber_g,
                    sugar_g = excluded.sugar_g,
                    sodium_mg = excluded.sodium_mg,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    menu_id,
                    nutrition["calories"],
                    nutrition["protein_g"],
                    nutrition["carbs_g"],
                    nutrition["fat_g"],
                    nutrition["fiber_g"],
                    nutrition["sugar_g"],
                    nutrition["sodium_mg"],
                ),
            )

        for key, value in DEFAULT_THEME_TOKENS.items():
            conn.execute(
                """
                INSERT INTO theme_config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    config_mod.update_business_config(config_mod.DEFAULT_BUSINESS_CONFIG)
    menu_mod.recalculate_menu_availability()


if __name__ == "__main__":
    from .db import reset_db

    reset_db()
    seed()
    print("Seeded El Camino Command data.")
