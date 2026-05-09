"""Seed the database with a Mexican-style food truck menu.

Menu, recipes, and starting inventory. Idempotent — safe to run on a
fresh DB. For demos, call reset_db() then seed().
"""
from .db import get_conn, init_db


MENU = [
    # name, price, category, description
    ("Carne Asada Taco",   3.50, "tacos",    "Grilled steak, onion, cilantro on corn tortilla"),
    ("Al Pastor Taco",     3.50, "tacos",    "Marinated pork with pineapple"),
    ("Veggie Taco",        3.00, "tacos",    "Black beans, peppers, queso fresco"),
    ("Carne Burrito",      9.50, "burritos", "Steak, rice, beans, salsa, cheese"),
    ("Veggie Burrito",     8.50, "burritos", "Beans, rice, peppers, queso fresco, salsa"),
    ("Chips & Guacamole",  5.00, "sides",    "Fresh tortilla chips with house guacamole"),
    ("Loaded Nachos",      8.00, "sides",    "Chips, beans, cheese, salsa, jalapeños"),
    ("Coke",               2.50, "drinks",   "12 oz can"),
    ("Lemonade",           3.00, "drinks",   "Fresh-squeezed"),
    ("Horchata",           3.50, "drinks",   "Cinnamon rice milk"),
]


# (ingredient, starting_qty, unit, reorder_threshold, cost_per_unit)
INVENTORY = [
    ("corn_tortilla",   1000, "pcs",  100,  0.10),
    ("flour_tortilla",  300,  "pcs",  50,   0.30),
    ("steak",           20000,"g",    3000, 0.025),
    ("pork",            15000,"g",    2500, 0.020),
    ("black_beans",     15000,"g",    2000, 0.005),
    ("rice",            12000,"g",    2000, 0.003),
    ("cheese",          8000, "g",    1500, 0.012),
    ("queso_fresco",    6000, "g",    1000, 0.018),
    ("onion",           8000, "g",    1500, 0.003),
    ("cilantro",        2000, "g",    400,  0.020),
    ("pineapple",       5000, "g",    1000, 0.005),
    ("avocado",         100,  "pcs",  20,   1.20),
    ("bell_peppers",    5000, "g",    1000, 0.006),
    ("jalapeno",        2000, "g",    400,  0.008),
    ("salsa",           8000, "g",    1500, 0.005),
    ("tortilla_chips",  12000,"g",    2500, 0.008),
    ("lime",            150,  "pcs",  30,   0.25),
    ("coke_can",        200,  "pcs",  40,   0.60),
    ("lemon",           100,  "pcs",  20,   0.40),
    ("rice_milk",       12000,"ml",   2500, 0.004),
    ("cinnamon",        500,  "g",    100,  0.030),
    ("sugar",           5000, "g",    1000, 0.002),
]


# menu_name -> [(ingredient, qty_per_serving), ...]
RECIPES = {
    "Carne Asada Taco":   [("corn_tortilla", 1), ("steak", 60), ("onion", 15), ("cilantro", 3), ("lime", 0.1)],
    "Al Pastor Taco":     [("corn_tortilla", 1), ("pork", 60), ("pineapple", 20), ("onion", 10), ("cilantro", 3)],
    "Veggie Taco":        [("corn_tortilla", 1), ("black_beans", 40), ("bell_peppers", 30), ("queso_fresco", 20)],
    "Carne Burrito":      [("flour_tortilla", 1), ("steak", 100), ("rice", 80), ("black_beans", 60), ("salsa", 30), ("cheese", 30)],
    "Veggie Burrito":     [("flour_tortilla", 1), ("black_beans", 100), ("rice", 80), ("bell_peppers", 50), ("queso_fresco", 30), ("salsa", 30)],
    "Chips & Guacamole":  [("tortilla_chips", 80), ("avocado", 1), ("onion", 10), ("lime", 0.25), ("cilantro", 2)],
    "Loaded Nachos":      [("tortilla_chips", 120), ("black_beans", 60), ("cheese", 50), ("salsa", 40), ("jalapeno", 15)],
    "Coke":               [("coke_can", 1)],
    "Lemonade":           [("lemon", 1), ("sugar", 20)],
    "Horchata":           [("rice_milk", 350), ("cinnamon", 2), ("sugar", 15)],
}


def seed():
    init_db()
    with get_conn() as conn:
        # Menu
        for name, price, category, desc in MENU:
            conn.execute(
                "INSERT OR IGNORE INTO menu (name, price, category, description) VALUES (?, ?, ?, ?)",
                (name, price, category, desc),
            )

        # Inventory
        for ingredient, qty, unit, threshold, cost in INVENTORY:
            conn.execute(
                """INSERT OR IGNORE INTO inventory
                   (ingredient, quantity, unit, reorder_threshold, cost_per_unit)
                   VALUES (?, ?, ?, ?, ?)""",
                (ingredient, qty, unit, threshold, cost),
            )

        # Recipes — need menu IDs
        name_to_id = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM menu")}
        for menu_name, items in RECIPES.items():
            menu_id = name_to_id[menu_name]
            for ingredient, qty in items:
                conn.execute(
                    """INSERT OR IGNORE INTO recipe (menu_id, ingredient, qty_per_serving)
                       VALUES (?, ?, ?)""",
                    (menu_id, ingredient, qty),
                )


if __name__ == "__main__":
    from .db import reset_db
    reset_db()
    seed()
    print("Seeded.")
