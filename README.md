# El Camino Command

Run the truck. Watch the numbers. Serve food on time.

El Camino Command is a Streamlit-based AI operating system for independent food trucks. It keeps deterministic business logic in Python/SQLite (orders, kitchen timing, inventory, COGS, revenue, profit, purchasing lifecycle) and uses LLMs only for voice parsing and owner Q&A with tools.

## What Changed

This version upgrades the original hackathon app into a command-center product while preserving the existing architecture.

- Centralized black/white/red command theme.
- Main command dashboard showing live operations + agent health.
- Kitchen timing engine that staggers item start offsets to finish hot together.
- Inventory expiry tracking with `ok/low/critical/out/expired/expires_today/expires_soon` states.
- Human-approved purchasing lifecycle (`suggested -> approved/rejected -> received`).
- Expanded analytics/money layer with COGS, purchase spend, estimated profit, risk summaries.
- New settings page for business config, menu timing, inventory thresholds/expiry, suppliers, theme tokens.
- New customer order status page by order number.
- Role-oriented views for Customer, Chef, Owner.

## Architecture

```text
streamlit_app.py
pages/
  1_🍽️_Order.py
  2_👨‍🍳_Kitchen.py
  3_📦_Inventory.py
  4_📊_Sales.py
  5_💰_Revenue.py
  6_🤖_Assistant.py
  7_⚙️_Settings.py
  8_🛒_Purchasing.py
  9_🔎_Order_Status.py
backend/
  db.py
  seed.py
  orders.py
  inventory.py
  payments.py
  analytics.py
  agents.py
  demo_data.py
  bootstrap.py
  config.py
  menu.py
  kitchen.py
  purchasing.py
  agent_status.py
  theme.py
  theme_tokens.py
data/foodtruck.db
```

## Deterministic Core

The following stay deterministic and do not depend on LLM calls:

- Order totals
- Inventory deduction and availability gating
- Kitchen timing and ETA
- COGS and profit estimates
- Purchasing approval and receiving lifecycle
- Revenue and supplier spending analytics

LLMs are used only for:

- Voice-to-cart parsing (Whisper + Llama)
- Owner assistant natural-language reasoning over backend tools

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
streamlit run streamlit_app.py
```

Optional demo history:

```bash
python -m backend.demo_data
```

## Command Dashboard Highlights

- Top status bar: open/closed, revenue today, orders today, active orders, alerts, estimated profit.
- Agent status cards:
  - Customer Kiosk Order Agent
  - Inventory + Supplies Purchasing Agent
  - Analytics + Money Agent
  - Kitchen Order Monitoring Agent
- Live panels: orders, kitchen timing, inventory alerts, purchase suggestions, money snapshot, agent event feed.

## Key Operational Features

### Kitchen Timing Engine

For each order item:

- `total_time = prep_time_minutes + cook_time_minutes` (quantity-scaled prototype logic)
- Longest item is anchor (`start_offset = 0`)
- Shorter items start later (`longest - item_total`)
- Timeline steps are stored in `kitchen_timeline_steps`
- `orders.estimated_ready_at` is written from deterministic ETA logic

### Inventory + Expiry Safety

Inventory is classified into explicit states and expired ingredients block dependent menu items until replaced or corrected.

### Human-Approved Purchasing

Purchasing behavior is now approval-based:

- Suggestions do not change inventory
- PO creation does not change inventory
- PO approval does not change inventory
- Only `mark_purchase_order_received()` increases inventory

### Analytics + Money

Analytics includes:

- Revenue, order count, average ticket
- COGS by order/day
- Purchase spending
- Estimated profit
- Profit over time
- Supplier spending
- Waste/inventory risk summaries

## Demo Script

1. Reset DB.
2. Load demo data.
3. Open dashboard and show agent cards.
4. Place order from customer page using buttons or voice.
5. Show order number and estimated wait time.
6. Open kitchen page and show staggered timeline.
7. Start/ready/complete order.
8. Open inventory and show deducted ingredients, low stock, expiry warnings.
9. Open purchasing and create/approve/receive a mock purchase order.
10. Open analytics and show revenue, COGS, profit, spending, top items.
11. Ask assistant: “What needs attention right now?”
12. Ask assistant: “Create purchase orders for the urgent restocks.”
13. Show tool calls and human approval behavior.
14. Open Customer View → Macros.
15. Create or select a customer macro profile and save deterministic targets.
16. View today’s macro dashboard, progress bars, pie chart, and 7-day history.
17. Open “Build My Macro Order,” choose one meal or whole day, and add the recommended real-menu items to cart.
18. Place the order with macro tracking enabled.
19. Return to Macros to show the order logged into history and updated charts.
20. Ask: “What should I order later today to stay on track?” The macro agent explains only recommendations grounded in current menu nutrition.
21. Open the owner dashboard/autopilot pages to show Customer Macro Agent activity and macro demand metrics.

## Product Positioning

El Camino Command helps independent food trucks take orders, time kitchen work, prevent stockouts, reduce waste, manage supplier restocking, and understand profit from one live dashboard.
