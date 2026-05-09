"""Generate a few days of fake order history so the dashboards have data.

Run: python -m backend.demo_data
"""
import random
from datetime import datetime, timedelta
from .db import get_conn, reset_db
from .seed import seed
from . import orders as orders_mod
from . import payments as payments_mod
from . import inventory as inv_mod


def generate(days: int = 7, orders_per_day_range: tuple[int, int] = (12, 28)):
    reset_db()
    seed()

    menu = orders_mod.get_menu()

    # Weighted popularity so some items become "best-sellers"
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

    names = ["Maria", "Jake", "Priya", "Carlos", "Aisha", "Tom", "Lin",
             "David", "Sofia", "Ahmed", "Emma", "Ravi", "Yuki", "Sam", "Mia"]

    today = datetime.now()
    total_orders = 0
    for d in range(days, 0, -1):
        day = today - timedelta(days=d - 1)
        n = random.randint(*orders_per_day_range)
        for _ in range(n):
            # 1-4 line items per order
            cart = []
            for _ in range(random.randint(1, 4)):
                item = random.choice(weighted_items)
                qty = random.choices([1, 2, 3], weights=[6, 3, 1])[0]
                cart.append({"menu_id": item["id"], "quantity": qty})

            # Compute total without inventory check (skip the agent path,
            # write directly so we can backdate timestamps)
            with get_conn() as conn:
                price_lookup = {m["id"]: m["price"] for m in menu}
                total = sum(price_lookup[c["menu_id"]] * c["quantity"] for c in cart)

                # Random timestamp within the day
                hour = random.randint(11, 21)
                minute = random.randint(0, 59)
                ts = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                ts_iso = ts.strftime("%Y-%m-%d %H:%M:%S")

                pay = payments_mod.charge(total, random.choice(names))
                if pay["status"] != "succeeded":
                    continue

                cur = conn.execute(
                    """INSERT INTO orders
                       (customer_name, status, total, payment_status, payment_id, created_at, completed_at)
                       VALUES (?, 'completed', ?, 'paid', ?, ?, ?)""",
                    (random.choice(names), total, pay["payment_id"], ts_iso, ts_iso),
                )
                order_id = cur.lastrowid
                for c in cart:
                    name = next(m["name"] for m in menu if m["id"] == c["menu_id"])
                    price = price_lookup[c["menu_id"]]
                    conn.execute(
                        """INSERT INTO order_items (order_id, menu_id, quantity, unit_price)
                           VALUES (?, ?, ?, ?)""",
                        (order_id, c["menu_id"], c["quantity"], price),
                    )
            # Deduct inventory after committing the order
            inv_mod.deduct_for_order(order_id)
            total_orders += 1

    print(f"Generated {total_orders} orders across {days} days.")


if __name__ == "__main__":
    generate(days=7, orders_per_day_range=(15, 30))
