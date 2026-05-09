"""Groq-powered agents.

Two agents:
1. CustomerVoiceAgent — transcribes voice via Whisper, parses speech
   into structured cart edits (add/remove items, modify quantities, notes).
2. OwnerAssistant — answers natural-language questions about the
   business by calling analytics/inventory tools.

Both use Groq. Set GROQ_API_KEY in env.
"""
import json
import os
from typing import Any

from groq import Groq

from . import analytics, inventory as inv_mod, orders as orders_mod


# Groq's currently-recommended models. If these get deprecated, swap below.
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
    """Run Groq Whisper on raw audio bytes. Returns the transcript text."""
    client = _client()
    resp = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=WHISPER_MODEL,
        response_format="text",
    )
    # Groq returns either a string or an object with .text depending on format
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
    """Parse a transcript into structured cart actions.

    Returns {"actions": [...], "reply": "..."} or
    {"actions": [], "reply": "...", "error": "..."} on parse failure.
    """
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
    """Apply parsed actions to a cart. Cart items are
    {menu_id, name, price, quantity, notes}."""
    menu = {m["name"].lower(): m for m in orders_mod.get_menu()}
    cart = [dict(c) for c in cart]

    for action in actions:
        op = action.get("op")
        item_name = (action.get("item") or "").strip().lower()
        if not item_name and op != "modify":
            continue
        menu_item = menu.get(item_name)
        # Try a fuzzy fallback — first menu name that contains the spoken phrase or vice versa
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
            # Merge with existing line if same item & same notes
            merged = False
            for c in cart:
                if c["menu_id"] == menu_item["id"] and c.get("notes") == notes:
                    c["quantity"] += qty
                    merged = True
                    break
            if not merged:
                cart.append({
                    "menu_id": menu_item["id"],
                    "name": menu_item["name"],
                    "price": menu_item["price"],
                    "quantity": qty,
                    "notes": notes,
                })
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
# Owner assistant — tool-using agent
# --------------------------------------------------------------------------

OWNER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_today_summary",
            "description": "Today's order count, revenue, and average ticket size.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_by_item",
            "description": "Units sold and revenue per menu item over the last N days.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 7}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_by_day",
            "description": "Daily revenue and order count over the last N days.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 30}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock",
            "description": "Inventory items at or below their reorder threshold.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_restock_suggestions",
            "description": "Suggested restock quantities and estimated costs for low-stock items.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_restock_order",
            "description": "Place a restock order for an ingredient with the supplier (Walmart mock).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string"},
                    "quantity": {"type": "number"},
                },
                "required": ["ingredient", "quantity"],
            },
        },
    },
]


def _exec_tool(name: str, args: dict) -> Any:
    if name == "get_today_summary":
        return analytics.today_summary()
    if name == "get_sales_by_item":
        return analytics.sales_by_item(days=args.get("days", 7))
    if name == "get_revenue_by_day":
        return analytics.revenue_by_day(days=args.get("days", 30))
    if name == "get_low_stock":
        return inv_mod.get_low_stock()
    if name == "get_restock_suggestions":
        return inv_mod.suggest_restocks()
    if name == "place_restock_order":
        return inv_mod.place_restock_order(args["ingredient"], args["quantity"])
    return {"error": f"unknown tool {name}"}


OWNER_SYSTEM = """You are the operations assistant for a food truck owner.

You have tools to query today's sales, item rankings, revenue trends,
inventory levels, and to place restock orders. Use them to give concrete,
data-backed answers. Be brief — owners are busy.

When suggesting restocks, always confirm with the owner before calling
place_restock_order. After placing one, summarize what was ordered and
the cost. Use dollar amounts where relevant. Don't make up numbers."""


def owner_chat(messages: list[dict], max_iterations: int = 5) -> dict:
    """Run a tool-using conversation. messages is OpenAI-style chat history.

    Returns {"reply": str, "tool_calls": [...]} where tool_calls is the
    sequence of (name, args, result) tuples for transparency in the UI.
    """
    client = _client()
    full_messages = [{"role": "system", "content": OWNER_SYSTEM}] + messages
    tool_trace = []

    for _ in range(max_iterations):
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=full_messages,
            tools=OWNER_TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"reply": msg.content or "", "tool_calls": tool_trace}

        # Append the assistant's tool-call message verbatim
        full_messages.append({
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
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _exec_tool(tc.function.name, args)
            tool_trace.append({"name": tc.function.name, "args": args, "result": result})
            full_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    return {"reply": "(stopped — too many tool iterations)", "tool_calls": tool_trace}
