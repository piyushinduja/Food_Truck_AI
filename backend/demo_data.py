"""Generate fake order history so dashboards have useful data.

Run: python -m backend.demo_data
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .db import get_conn, reset_db
from .seed import seed
from . import macros as macros_mod
from . import orders as orders_mod
from . import payments as payments_mod
from . import inventory as inv_mod
from . import kitchen as kitchen_mod


def generate(days: int = 7, orders_per_day_range: tuple[int, int] = (12, 28)) -> None:
    reset_db()
    seed()

    menu = orders_mod.get_menu()

    weights = {
        "Carne Asada Taco": 5,
        "Al Pastor Taco": 4,
        "Veggie Taco": 2,
        "Carne Burrito": 3,
        "Veggie Burrito": 2,
        "Chips & Guacamole": 3,
        "Loaded Nachos": 2,
        "Coke": 4,
        "Lemonade": 2,
        "Horchata": 1,
    }
    weighted_items = []
    for m in menu:
        weighted_items.extend([m] * weights.get(m["name"], 1))

    names = [
        "Maria",
        "Jake",
        "Priya",
        "Carlos",
        "Aisha",
        "Tom",
        "Lin",
        "David",
        "Sofia",
        "Ahmed",
        "Emma",
        "Ravi",
        "Yuki",
        "Sam",
        "Mia",
    ]

    today = datetime.now()
    total_orders = 0
    order_counter = 2000
    macro_profile = macros_mod.find_or_create_customer_by_name_phone(
        "Marco Ramirez",
        "555-0198",
        email="marco@example.com",
        height_cm=178,
        weight_kg=82,
        age=34,
        sex="male",
        activity_level="moderate",
        goal="high protein",
    )

    for d in range(days, 0, -1):
        day = today - timedelta(days=d - 1)
        target_date = day.date().isoformat()
        macros_mod.save_macro_targets(
            macro_profile["id"],
            target_date,
            macros_mod.calculate_macro_targets(macro_profile),
        )
        n = random.randint(*orders_per_day_range)
        for _ in range(n):
            cart = []
            for _ in range(random.randint(1, 4)):
                item = random.choice(weighted_items)
                qty = random.choices([1, 2, 3], weights=[6, 3, 1])[0]
                cart.append({"menu_id": item["id"], "quantity": qty})

            with get_conn() as conn:
                price_lookup = {m["id"]: m["price"] for m in menu}
                total = sum(price_lookup[c["menu_id"]] * c["quantity"] for c in cart)

                hour = random.randint(11, 21)
                minute = random.randint(0, 59)
                ts = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                ts_iso = ts.strftime("%Y-%m-%d %H:%M:%S")

                pay = payments_mod.charge(total, random.choice(names))
                if pay["status"] != "succeeded":
                    continue

                order_counter += 1
                order_number = f"EC-{order_counter:04d}"
                cur = conn.execute(
                    """
                    INSERT INTO orders
                    (order_number, customer_name, status, total, payment_status, payment_id, source, created_at, completed_at)
                    VALUES (?, ?, 'completed', ?, 'paid', ?, 'kiosk', ?, ?)
                    """,
                    (order_number, random.choice(names), total, pay["payment_id"], ts_iso, ts_iso),
                )
                order_id = cur.lastrowid

                for c in cart:
                    price = price_lookup[c["menu_id"]]
                    conn.execute(
                        """
                        INSERT INTO order_items (order_id, menu_id, quantity, unit_price)
                        VALUES (?, ?, ?, ?)
                        """,
                        (order_id, c["menu_id"], c["quantity"], price),
                    )

            inv_mod.deduct_for_order(order_id)
            kitchen_mod.save_kitchen_timeline(order_id)
            with get_conn() as conn:
                conn.execute(
                    "UPDATE orders SET status='completed', completed_at=? WHERE id=?",
                    (ts_iso, order_id),
                )
            if random.random() < 0.22:
                macros_mod.log_order_macros(macro_profile["id"], order_id)
            total_orders += 1

    print(f"Generated {total_orders} orders across {days} days.")


if __name__ == "__main__":
    generate(days=7, orders_per_day_range=(15, 30))
