# El Camino Command

> AI-powered operating system for independent food trucks.

El Camino Command is a full-stack Streamlit application that combines a deterministic Python/SQLite core (orders, kitchen timing, inventory, purchasing, analytics) with Groq-powered AI agents (voice ordering, owner assistant, customer macro recommendations, autopilot). It runs as a single app with two connected experiences — a customer kiosk and an owner command center — sharing the same live database.

---

## Feature Overview

### Customer Experience
| Feature | Description |
|---|---|
| **Kiosk Ordering** | Browse menu by category (Popular, Burritos, Tacos, Sides, Drinks), add items with native buttons, no page reloads |
| **Cart Management** | Quantity controls, per-item removal, live subtotal + tax calculation |
| **Ready-By Time** | Cart shows estimated pickup clock time (`now + wait`) in local timezone |
| **Voice Ordering** | Text or audio input parsed by Groq Whisper + Llama into structured cart actions |
| **Order Tracking** | Order status lookup by order number on a dedicated page |
| **Macro Tracking** | Optional per-order macro logging against a customer profile |

### Owner Command Center
| Feature | Description |
|---|---|
| **Command Dashboard** | Live KPIs, kitchen queue, inventory health donut chart, purchasing queue, money snapshot, agent activity feed |
| **Kitchen Page** | Order cards with status pill, ETA in local time, prep timeline progress bar, Start / Ready / Complete buttons |
| **Inventory Page** | Status bar chart, full ingredient table, expiry risk, alerts, purchasing suggestions |
| **Purchasing Page** | Suggested restocks → Create PO → Approve → Mark Received lifecycle with mock supplier data |
| **Sales Analytics** | Top/bottom sellers, category revenue donut, high-protein item demand, macro conversion metrics |
| **Revenue / Money** | Revenue by day, profit trend, supplier spending breakdown, COGS, waste risk value |
| **Owner Assistant** | Tool-calling LLM grounded on live backend data; handles dashboard, inventory, purchasing, profit, kitchen Q&A |
| **Autopilot** | Three autonomy modes (Manual / Assist / Full) with agent grid and action feed |
| **Daily Report** | Executive briefing with performance highlights, inventory alerts, agent actions, tomorrow prep plan |
| **Settings** | Business config, tax rate, open/closed toggle, prep buffer, expiry warning days, supplier editor, theme tokens |

### Customer Macro System
| Feature | Description |
|---|---|
| **Profile Builder** | Height, weight, age, sex, activity level, goal (maintain / lose weight / gain muscle / high protein / custom) |
| **Target Calculator** | Mifflin-St Jeor BMR → TDEE × multiplier → goal-adjusted calories, protein, carbs, fat |
| **Daily Dashboard** | Progress bars + donut chart for consumed vs. target vs. remaining; 7-day calorie history |
| **Macro Order Builder** | One-meal or whole-day recommendation engine; 8 strategies (balanced, high protein, lower carb, etc.) |
| **Cart Swaps** | Suggest alternative items to hit remaining macro targets |
| **AI Explanation** | Groq-powered narrative explaining why a recommendation fits the customer's current macros |
| **Order Logging** | Each placed order (with tracking enabled) updates the customer's daily macro summary |

---

## AI Agents

### 1 — Customer Voice Agent
- Transcribes audio with **Groq Whisper** (`whisper-large-v3-turbo`)
- Parses natural-language order changes (add / remove / modify / notes) with **Llama 3.3 70B**
- Returns structured JSON cart actions; merges with existing cart state

### 2 — Customer Macro Agent
- Computes BMR/TDEE from customer biometrics
- Runs a combinatorial meal recommender against real menu nutrition data
- Generates AI narrative explaining the recommendation
- Logs suggestions to `macro_ai_suggestions` table

### 3 — Owner Assistant (Tool-Calling Agent)
- Uses Groq function-calling with 11 registered tools:
  - `get_dashboard_summary`, `get_inventory_alerts`, `get_expiring_inventory`
  - `get_purchase_orders`, `create_purchase_order_from_suggestion`
  - `approve_purchase_order`, `mark_purchase_order_received`
  - `get_profit_summary`, `get_kitchen_queue`, `get_late_orders`
  - `create_instacart_restock_link`
- Mutating tools require explicit owner intent detected in the message text
- All facts and numbers come from deterministic backend queries — LLM never invents data

### 4 — Autopilot (Deterministic Orchestrator)
Three modes selectable at runtime:

| Mode | Behavior |
|---|---|
| **Manual** | No autonomous actions |
| **Assist** | Flags late orders, advances one pending order to preparing, drafts POs for critical ingredients |
| **Full Autopilot** | Everything in Assist + auto-approves and auto-receives POs when human approval is disabled |

All actions are logged to `agent_events` and visible in the action feed.

---

## Instacart Integration

`backend/instacart.py` generates a real Instacart shopping-list URL from current low-stock ingredients.

- Calls **Instacart Developer Platform** (`POST /idp/v1/products/products_link`)
- Normalises units (g→kg at 1000+, ml→l at 1000+) and maps internal names to grocery product names
- Falls back gracefully to an Instacart search URL if no API key is present
- Accessible from the Owner Assistant ("create instacart restock link") or directly via code

---

## Architecture

```
streamlit_app.py              ← Entry point; Customer / Owner view selector
_path_setup.py

pages/
  0_🧭_Command_Dashboard.py  ← Owner KPI overview
  1_🍽️_Order.py              ← Customer kiosk (cart state lives in session_state)
  2_👨‍🍳_Kitchen.py            ← Kitchen queue and timing controls
  3_📦_Inventory.py          ← Stock levels, expiry risk, restock suggestions
  4_📊_Sales.py              ← Sales analytics, macro demand metrics
  5_💰_Revenue.py            ← Revenue, profit, supplier spending
  6_🤖_Assistant.py          ← Owner tool-calling chat
  7_⚙️_Settings.py           ← Business config, suppliers, theme
  7_📋_Brief.py              ← Daily executive briefing
  8_🛒_Purchasing.py         ← PO lifecycle management
  9_🔎_Order_Status.py       ← Customer order lookup
  10_🧠_Autopilot.py         ← Autonomy mode controls and agent grid
  12_🥗_Customer_Macros.py   ← Profile, dashboard, order builder, history

backend/
  agents.py                  ← Groq voice + owner assistant + macro agent
  analytics.py               ← Revenue, COGS, profit, waste, supplier spend queries
  autopilot.py               ← Autopilot cycle, agent grid state, event logging
  bootstrap.py               ← App startup, .env loading, DB init, seeding
  brief.py                   ← Daily briefing data assembly
  config.py                  ← Business config persistence (SQLite)
  db.py                      ← SQLite schema, migrations, connection helper
  demo_data.py               ← 7-day fake order history generator
  instacart.py               ← Instacart Developer Platform integration
  inventory.py               ← Stock status, expiry classification, deduction
  kitchen.py                 ← Kitchen timeline engine, ETA calculation, queue
  macro_charts.py            ← Macro progress and history chart data
  macro_recommendations.py   ← Meal and full-day recommendation engine
  macros.py                  ← Customer profiles, targets, daily summaries
  menu.py                    ← Menu CRUD, availability gating
  nutrition.py               ← Menu nutrition data, cart nutrition calculation
  orders.py                  ← Order lifecycle (create → complete), status advance
  payments.py                ← Mock payment processor
  purchasing.py              ← PO creation, approval, receiving, suggestions
  seed.py                    ← Initial DB population (menu, inventory, suppliers)
  sms.py                     ← Twilio SMS integration (optional)
  theme.py                   ← UI component primitives
  theme_tokens.py            ← Color constants
  timing.py                  ← Per-item prep/cook time estimator
  ui_components.py           ← Shared Streamlit shell, nav, metric cards
  agent_status.py            ← Agent health indicators

data/foodtruck.db            ← SQLite database (17 tables)
.env                         ← API keys (gitignored)
```

---

## Database Schema (17 tables)

| Table | Purpose |
|---|---|
| `menu` | Menu items with pricing, timing, availability |
| `inventory` | Ingredients with quantity, thresholds, expiry |
| `recipe` | Menu item → ingredient mappings with qty per serving |
| `orders` | Order header (status, total, ETA, customer) |
| `order_items` | Line items per order |
| `kitchen_timeline_steps` | Per-item start offset and duration for kitchen display |
| `purchase_orders` | PO header with status lifecycle |
| `purchase_order_items` | Ingredients per PO |
| `suppliers` | Vendor info |
| `customer_profiles` | Customer biometrics and macro goals |
| `customer_macro_targets` | Calculated macro targets per date |
| `order_macro_logs` | Per-order macro contribution |
| `daily_macro_summaries` | Aggregated daily intake vs. target |
| `macro_ai_suggestions` | Stored AI macro recommendations |
| `menu_nutrition` | Calories, protein, carbs, fat, fiber, sugar, sodium |
| `business_config` | Key/value store for app settings |
| `agent_events` | Autopilot and agent action log |

---

## Deterministic Core

The following never depend on LLM calls:

- Order totals, tax, payment processing
- Inventory deduction and menu availability gating
- Kitchen timing, start-offset staggering, ETA calculation
- COGS, purchase spending, estimated profit
- PO approval and receiving lifecycle
- All analytics and chart data
- Macro target calculation (Mifflin-St Jeor formula)
- Meal recommendation scoring (combinatorial, no AI)

LLMs are used only for:

- Voice-to-cart parsing (Groq Whisper + Llama)
- Owner assistant natural-language Q&A over tool results
- Macro recommendation narrative explanation

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root (already present):

```
GROQ_API_KEY=gsk_...

# Optional
INSTACART_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
```

Run the app:

```bash
streamlit run streamlit_app.py
```

Load demo order history (optional but recommended for demos):

```bash
python -m backend.demo_data
```

> On Windows: if environment variables set via `setx` are not picked up, put them in the `.env` file — the app loads it automatically at startup.

---

## Kitchen Timing Engine

For each order:

1. Each item's `total_time = prep_time_minutes + cook_time_minutes` (quantity-scaled: each extra unit adds 60% of one cycle)
2. The longest item has `start_offset = 0` (starts immediately)
3. Shorter items have `start_offset = longest − item_total` so all items finish together
4. Timeline steps are saved to `kitchen_timeline_steps`
5. `estimated_ready_at` is stored in UTC and displayed in the user's local timezone

---

## Inventory Safety System

Every inventory item is classified into one of seven states:

`ok` → `low` → `critical` → `out` → `expires_soon` → `expires_today` → `expired`

- Expired or out-of-stock ingredients automatically mark dependent menu items as unavailable
- `recalculate_menu_availability()` runs after every inventory change
- Expiry warning window is configurable (default: 3 days)

---

## Purchasing Lifecycle

```
Suggested → Created → Approved → Received
```

- Suggestions are generated deterministically from inventory status
- Creating a PO does not touch inventory
- Approving a PO does not touch inventory
- Only `mark_purchase_order_received()` increases stock
- Human approval gate is configurable; Autopilot in Full mode can bypass it

---

## Demo Script

1. Open the app → **Reset Database** (Admin expander) → confirm seed loaded
2. Run `python -m backend.demo_data` to populate 7 days of order history
3. **Customer View** → place an order using category tabs and Add buttons
4. Show cart total, ready-by time, voice order expander
5. Check out → note order number → switch to **Order Status** page to track it
6. **Kitchen** → Start → Ready → Complete the order; watch ETA in local time
7. **Inventory** → show bar chart, low/expired ingredients, blocked menu items
8. **Purchasing** → create a mock PO for a critical ingredient → Approve → Mark Received
9. **Sales** → show top sellers, category mix, macro demand metrics
10. **Revenue** → show revenue trend, profit line, supplier spending
11. **Assistant** → "What needs attention right now?" (tool calls visible in expander)
12. **Assistant** → "Create a purchase order for steak" (intent gate demo)
13. **Assistant** → "Generate an Instacart restock link" → tap the URL
14. **Customer Macros** → create a profile with goal "high protein"
15. **Build My Macro Order** → one meal → add to cart
16. Place order with macro tracking enabled
17. Return to **Macro Dashboard** → show progress bars, updated history
18. "What should I order later today?" → macro AI suggestion
19. **Autopilot** → switch to Assist mode → Run Autopilot Cycle → show action feed
20. **Command Dashboard** → show macro demand section and agent activity

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI framework | Streamlit |
| Database | SQLite (via Python `sqlite3`) |
| LLM / Voice | Groq API (Llama 3.3 70B, Whisper large-v3-turbo) |
| Charts | Altair, Pandas |
| Shopping integration | Instacart Developer Platform |
| SMS (optional) | Twilio |
| Python | 3.11+ |

---

## Product Positioning

El Camino Command gives independent food truck operators a single live system to:

- Accept orders without paper or a third-party POS
- Time kitchen work so all items finish hot together
- Track inventory expiry before it becomes waste or a safety issue
- Manage supplier restocking with human approval gates or full autopilot
- Understand daily profit after COGS and purchasing spend
- Let customers track their nutrition goals across orders
- Ask an AI assistant grounded in real operational data
