"""Groq-powered agents.

1) Customer voice flow: transcription + structured cart parse.
2) Owner assistant: tool-using operations assistant over deterministic backend data.
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from groq import Groq

from . import analytics
from . import inventory as inv_mod
from . import kitchen
from . import macro_recommendations
from . import macros
from . import nutrition
from . import orders as orders_mod
from . import purchasing


TEXT_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL = "whisper-large-v3-turbo"


def _client() -> Groq:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return Groq(api_key=key)


# --------------------------------------------------------------------------
# Customer voice agent
# --------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes, filename: str = "input.wav") -> str:
    """Run Groq Whisper on raw audio bytes. Returns transcript text."""
    client = _client()
    resp = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=WHISPER_MODEL,
        response_format="text",
    )
    return resp if isinstance(resp, str) else resp.text


PARSE_SYSTEM = """You are an order-parsing assistant for a Mexican food truck.

The user will describe changes they want to make to their cart in natural speech.
You output a JSON object describing those changes. Do not output anything else.

Schema:
{
  "actions": [
    {"op": "add", "item": "<menu item name>", "quantity": <int>, "notes": "<str or null>"},
    {"op": "remove", "item": "<menu item name>", "quantity": <int or null for all>},
    {"op": "modify", "item": "<menu item name>", "notes": "<str>"}
  ],
  "reply": "<one short sentence to read back to the customer>"
}

Rules:
- Match the user's words to the closest item on the menu (provided below).
- If they say "no cilantro" or "extra cheese", that's a `modify` op (or a note on `add`).
- If you can't confidently match an item, omit it from actions and mention it in reply.
- Quantities default to 1.
- Output ONLY valid JSON, no markdown fences.
"""


def parse_voice_order(transcript: str, current_cart: list[dict] | None = None) -> dict:
    menu = orders_mod.get_menu()
    menu_str = "\n".join(f"- {m['name']} (${m['price']:.2f}) — {m['category']}" for m in menu)

    cart_str = "Cart is empty."
    if current_cart:
        cart_str = "Current cart:\n" + "\n".join(
            f"- {c['quantity']}x {c['name']}" + (f" ({c['notes']})" if c.get("notes") else "")
            for c in current_cart
        )

    user_msg = f"MENU:\n{menu_str}\n\n{cart_str}\n\nCUSTOMER SAID: {transcript}"

    client = _client()
    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        parsed = json.loads(content)
        parsed.setdefault("actions", [])
        parsed.setdefault("reply", "")
        return parsed
    except json.JSONDecodeError as e:
        return {"actions": [], "reply": "Sorry, I didn't catch that.", "error": str(e)}


def apply_actions_to_cart(cart: list[dict], actions: list[dict]) -> list[dict]:
    menu = {m["name"].lower(): m for m in orders_mod.get_menu()}
    cart = [dict(c) for c in cart]

    for action in actions:
        op = action.get("op")
        item_name = (action.get("item") or "").strip().lower()
        if not item_name and op != "modify":
            continue

        menu_item = menu.get(item_name)
        if not menu_item and item_name:
            for k, v in menu.items():
                if item_name in k or k in item_name:
                    menu_item = v
                    break
        if not menu_item:
            continue

        if op == "add":
            qty = int(action.get("quantity") or 1)
            notes = action.get("notes")
            merged = False
            for c in cart:
                if c["menu_id"] == menu_item["id"] and c.get("notes") == notes:
                    c["quantity"] += qty
                    merged = True
                    break
            if not merged:
                cart.append(
                    {
                        "menu_id": menu_item["id"],
                        "name": menu_item["name"],
                        "price": menu_item["price"],
                        "quantity": qty,
                        "notes": notes,
                    }
                )

        elif op == "remove":
            qty = action.get("quantity")
            for c in list(cart):
                if c["menu_id"] == menu_item["id"]:
                    if qty is None or c["quantity"] <= qty:
                        cart.remove(c)
                    else:
                        c["quantity"] -= qty
                    break

        elif op == "modify":
            for c in cart:
                if c["menu_id"] == menu_item["id"]:
                    c["notes"] = action.get("notes") or c.get("notes")
                    break

    return cart


# --------------------------------------------------------------------------
# Customer macro agent
# --------------------------------------------------------------------------

MACRO_SYSTEM = """You are El Camino's customer macro ordering assistant.

Rules:
- Use only the menu items and nutrition values in the provided data.
- Do not invent food items, calories, protein, carbs, or fat values.
- If the current menu cannot satisfy a target, say so clearly.
- Give practical food-order suggestions using available items only.
- Keep advice short and focused on ordering.
- Do not give medical advice, health claims, or weight-loss guarantees.
"""


def _save_macro_suggestion(customer_id: int | None, suggestion_date: str, context: dict, suggestion: str, recommended_items: list[dict] | None = None) -> None:
    from .db import get_conn

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO macro_ai_suggestions (
                customer_id, suggestion_date, context, suggestion, recommended_items_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                suggestion_date,
                json.dumps(context, default=str),
                suggestion,
                json.dumps(recommended_items or [], default=str),
            ),
        )


def _macro_chat(context: dict, prompt: str) -> str:
    client = _client()
    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": MACRO_SYSTEM},
            {"role": "user", "content": json.dumps({"context": context, "request": prompt}, default=str)},
        ],
        temperature=0.15,
    )
    return resp.choices[0].message.content or ""


def macro_suggestion_agent(customer_id: int, target_date: str) -> dict:
    recommendation = macro_recommendations.recommend_meal_for_macros(customer_id, target_date, "use today remaining")
    context = {
        "daily_summary": macros.get_daily_macro_summary(customer_id, target_date),
        "history_7d": macros.get_macro_history(customer_id, days=7),
        "available_menu": nutrition.list_menu_with_nutrition(include_unavailable=False),
        "recommendation": recommendation,
    }
    reply = _macro_chat(context, "What should this customer order later today to stay on track?")
    _save_macro_suggestion(
        customer_id,
        target_date,
        context,
        reply,
        (recommendation.get("recommendation") or {}).get("recommended_items", []),
    )
    from .autopilot import log_agent_event

    log_agent_event("Customer Macro Agent", "healthy", "Macro suggestion generated", f"AI suggestion generated for customer #{customer_id}.", "Macro Suggestion")
    return {"reply": reply, "context": context}


def explain_macro_order_recommendation(customer_id: int, recommendation: dict) -> dict:
    target_date = date.today().isoformat()
    context = {
        "daily_summary": macros.get_daily_macro_summary(customer_id, target_date),
        "available_menu": nutrition.list_menu_with_nutrition(include_unavailable=False),
        "recommendation": recommendation,
    }
    reply = _macro_chat(context, "Explain why this recommendation fits the customer's macro target.")
    _save_macro_suggestion(customer_id, target_date, context, reply, recommendation.get("recommended_items", []))
    return {"reply": reply, "context": context}


def suggest_macro_cart_swaps(customer_id: int, cart_items: list[dict]) -> dict:
    target_date = date.today().isoformat()
    swaps = macro_recommendations.suggest_macro_swaps(cart_items, customer_id, target_date)
    context = {
        "daily_summary": macros.get_daily_macro_summary(customer_id, target_date),
        "available_menu": nutrition.list_menu_with_nutrition(include_unavailable=False),
        "swaps": swaps,
    }
    reply = _macro_chat(context, "Suggest grounded cart swaps for this macro target.")
    _save_macro_suggestion(customer_id, target_date, context, reply, swaps.get("alternatives", []))
    return {"reply": reply, "context": context}


# --------------------------------------------------------------------------
# Owner assistant — tool-using agent
# --------------------------------------------------------------------------

OWNER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": "Get key KPI summary for revenue, orders, cogs, profit, alerts, and active ops.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_alerts",
            "description": "Get low/critical/out/expiry inventory alerts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiring_inventory",
            "description": "Get inventory that is expired or expiring within N days.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 3}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_purchase_orders",
            "description": "List purchase orders and their statuses.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_order_from_suggestion",
            "description": "Draft a purchase order for one ingredient and quantity. Owner explicit instruction required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string"},
                    "quantity": {"type": "number"},
                    "supplier_id": {"type": "integer"},
                },
                "required": ["ingredient", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_purchase_order",
            "description": "Approve a drafted purchase order. Owner explicit instruction required.",
            "parameters": {
                "type": "object",
                "properties": {"purchase_order_id": {"type": "integer"}},
                "required": ["purchase_order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_purchase_order_received",
            "description": "Mark an approved purchase order as received and add inventory. Owner explicit instruction required.",
            "parameters": {
                "type": "object",
                "properties": {"purchase_order_id": {"type": "integer"}},
                "required": ["purchase_order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profit_summary",
            "description": "Get deterministic revenue, cogs, purchase spending, and estimated profit metrics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kitchen_queue",
            "description": "Get active kitchen queue with timing state and late flags.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_late_orders",
            "description": "Get currently late kitchen orders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


MUTATING_TOOLS = {
    "create_purchase_order_from_suggestion",
    "approve_purchase_order",
    "mark_purchase_order_received",
}


def _exec_tool(name: str, args: dict, allow_mutation: bool) -> Any:
    if name in MUTATING_TOOLS and not allow_mutation:
        return {
            "ok": False,
            "error": "owner_confirmation_required",
            "message": "This purchase action needs explicit owner approval in the request.",
        }

    if name == "get_dashboard_summary":
        return analytics.dashboard_summary()
    if name == "get_inventory_alerts":
        return inv_mod.get_inventory_alerts()
    if name == "get_expiring_inventory":
        return inv_mod.get_expiring_inventory(days=args.get("days"))
    if name == "get_purchase_orders":
        return purchasing.list_purchase_orders(status=args.get("status"))
    if name == "create_purchase_order_from_suggestion":
        return purchasing.create_purchase_order_from_suggestion(
            ingredient=args["ingredient"],
            quantity=args["quantity"],
            supplier_id=args.get("supplier_id"),
        )
    if name == "approve_purchase_order":
        return purchasing.approve_purchase_order(args["purchase_order_id"])
    if name == "mark_purchase_order_received":
        return purchasing.mark_purchase_order_received(args["purchase_order_id"])
    if name == "get_profit_summary":
        return {
            "today": analytics.today_summary(),
            "cogs_today": analytics.cogs_today(),
            "purchase_spending_30d": analytics.purchase_spending(days=30),
            "estimated_profit_today": analytics.estimated_profit_today(),
            "profit_by_day_30d": analytics.profit_by_day(days=30),
        }
    if name == "get_kitchen_queue":
        return kitchen.get_active_kitchen_orders()
    if name == "get_late_orders":
        return [o for o in kitchen.get_active_kitchen_orders() if o.get("is_late")]
    return {"error": f"unknown_tool:{name}"}


def _explicit_owner_intent(user_text: str, tool_name: str) -> bool:
    text = (user_text or "").lower()

    if tool_name == "create_purchase_order_from_suggestion":
        return any(
            phrase in text
            for phrase in [
                "create purchase",
                "draft purchase",
                "create po",
                "create order",
                "restock order",
                "order restock",
                "purchase order",
            ]
        )

    if tool_name == "approve_purchase_order":
        return any(phrase in text for phrase in ["approve", "go ahead", "confirm", "ok to approve"])

    if tool_name == "mark_purchase_order_received":
        return any(
            phrase in text
            for phrase in [
                "mark received",
                "received",
                "mark delivered",
                "delivery received",
                "stock received",
            ]
        )

    return True


OWNER_SYSTEM = """You are El Camino Command's owner assistant.

Rules:
- Be brief.
- Use tool data for all numbers and facts.
- Never invent values.
- For purchasing, do not create/approve/receive unless the owner explicitly asks.
- Before purchase lifecycle actions, explain estimated cost impact.
- Expired ingredients are unsafe until replaced or expiry is corrected.
"""


def owner_chat(messages: list[dict], max_iterations: int = 6) -> dict:
    """Run a tool-using owner chat loop.

    Returns {"reply": str, "tool_calls": list[dict]}.
    """
    client = _client()
    full_messages = [{"role": "system", "content": OWNER_SYSTEM}] + messages
    tool_trace: list[dict] = []

    latest_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            latest_user = m.get("content", "")
            break

    for _ in range(max_iterations):
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=full_messages,
            tools=OWNER_TOOLS,
            tool_choice="auto",
            temperature=0.15,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"reply": msg.content or "", "tool_calls": tool_trace}

        full_messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            allow_mutation = _explicit_owner_intent(latest_user, tc.function.name)
            result = _exec_tool(tc.function.name, args, allow_mutation=allow_mutation)
            tool_trace.append({"name": tc.function.name, "args": args, "result": result})

            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    return {"reply": "(stopped after max tool iterations)", "tool_calls": tool_trace}
