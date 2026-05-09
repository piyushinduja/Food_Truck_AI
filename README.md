# 🌮 El Camino — Run-Your-Business AI for Food Trucks

A hackathon project that turns a Streamlit app into a fully agentic operations console for a food truck: voice-driven ordering, automatic inventory deduction, supplier restocks, and a tool-using owner assistant.

## What's inside

**Customer side** — a click menu plus voice ordering. The customer can tap items or hit the mic and say _"two carne tacos and a coke, no cilantro on one"_ — Groq Whisper transcribes, Llama parses into structured cart edits, the cart updates.

**Owner side** — five dashboards (Kitchen, Inventory, Sales, Revenue) plus a chat assistant that has function-calling access to the same data. Ask _"what's running low?"_ or _"order more steak"_ and it queries the DB and places restocks.

## Architecture

```
streamlit_app.py          # entry, landing page, sidebar reset
pages/                    # Streamlit auto-discovers these
  1_🍽️_Order.py            # customer menu + voice
  2_👨‍🍳_Kitchen.py          # active orders queue
  3_📦_Inventory.py        # stock levels + restock
  4_📊_Sales.py            # item rankings
  5_💰_Revenue.py          # daily revenue
  6_🤖_Assistant.py        # tool-using owner agent
backend/
  db.py                   # SQLite schema + connection
  seed.py                 # menu, ingredients, recipes
  orders.py               # create_order, lifecycle
  inventory.py            # deduct, low-stock, mock Walmart
  payments.py             # mock Stripe
  analytics.py            # SQL aggregations
  agents.py               # Groq Whisper + chat + tools
  demo_data.py            # backdated fake orders
data/foodtruck.db         # auto-created on first run
```

**Design philosophy.** Order/inventory/sales/revenue are deterministic Python — not LLM-wrapped. The LLM only shows up where natural language actually adds value: parsing voice into cart edits, and answering owner questions with tool-calls. This keeps the system fast, debuggable, and demoable.

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
python -m backend.demo_data    # optional: populate dashboards with 7 days of fake orders
streamlit run streamlit_app.py
```

If you skip `demo_data`, the DB seeds itself on first launch with menu/inventory only — dashboards will be empty until you place orders.

## Demo script (5 min)

1. **Sidebar → Reset Database**, then run `python -m backend.demo_data` so dashboards have history.
2. **Order page** → tap a few items → hit the mic → say _"add two carne asada tacos and a horchata"_ → cart updates → enter name → place order.
3. **Kitchen page** → new order at the top with a live timer → click Start Preparing → Mark Ready → Mark Completed.
4. **Inventory page** → notice items now have lower stock; if any went low, click Order to restock.
5. **Sales page** → bar chart of best-sellers and category pie.
6. **Revenue page** → daily revenue bars.
7. **Assistant page** → ask _"what's running low and what would it cost to restock?"_ → watch the tool calls in the expander → ask _"go ahead and order all of those"_.

## Pluggable integrations

- **Stripe** — replace `backend/payments.py:charge()` with `stripe.PaymentIntent.create()`. Return shape is already compatible.
- **Walmart / Instacart Connect** — replace `backend/inventory.py:place_restock_order()`. Return shape: `{ok, confirmation_id, ingredient, quantity, unit, cost}`.
- **Twilio (SMS notifications)** — emit on `orders.advance_status()` when status flips to `ready`.

## What the agents actually do

**Customer voice agent** (`agents.parse_voice_order`)
- Input: raw transcript + current cart + menu
- Output: structured `actions: [{op, item, quantity, notes}]` + spoken reply
- Why an agent? Because "make the second taco no onions" doesn't map cleanly to clicks.

**Owner assistant** (`agents.owner_chat`)
- Tools: `get_today_summary`, `get_sales_by_item`, `get_revenue_by_day`, `get_low_stock`, `get_restock_suggestions`, `place_restock_order`
- Loops up to 5 turns of tool calls before answering.
- Why an agent? Because owners ask compound questions like _"how's today vs last week, and is anything running low?"_ that need 2-3 tool hits.
