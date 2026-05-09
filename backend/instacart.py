"""Instacart Developer Platform — shoppable list link generator.

Creates a real Instacart shopping list URL for a list of ingredients.
The owner taps the link, picks a store (Walmart, Costco, local grocer,
etc), and checks out in the Instacart app. Real food gets delivered.

Endpoint: POST /idp/v1/products/products_link
Docs: https://docs.instacart.com/developer_platform_api/

Setup:
  1. Sign up at https://docs.instacart.com/developer_platform_api/get_started/overview/
  2. Get a dev API key from the dashboard.
  3. export INSTACART_API_KEY=...
  4. (Optional) export INSTACART_ENV=dev   # or "prod" once you're approved

Without a key, this falls back to a plain Instacart search URL — still
a working link, just without the pre-built cart. The function shape
stays the same so the rest of the app doesn't care.
"""
from __future__ import annotations

import os
import urllib.parse
from typing import Optional

import requests


# ---- API config ----
DEV_BASE = "https://connect.dev.instacart.tools"
PROD_BASE = "https://connect.instacart.com"
ENDPOINT = "/idp/v1/products/products_link"
DEFAULT_TIMEOUT = 15


def _base_url() -> str:
    env = os.environ.get("INSTACART_ENV", "dev").lower()
    return PROD_BASE if env == "prod" else DEV_BASE


# ---- Unit translation ----
# Instacart's accepted units are limited. Translate our internal units
# to what their API accepts, defaulting to "each" when unsure.
# Reference: https://docs.instacart.com/.../shopping_list/#units-of-measurement
UNIT_MAP = {
    "g":    "gram",
    "kg":   "kilogram",
    "ml":   "milliliter",
    "l":    "liter",
    "pcs":  "each",
    "each": "each",
    "lb":   "pound",
    "oz":   "ounce",
}


def _translate_unit(unit: str) -> str:
    return UNIT_MAP.get(unit.lower(), "each")


# ---- Quantity sensible-ifying ----
# An ingredient like "steak" might be tracked as 9000g internally.
# Asking Instacart for "9000 grams of steak" is silly — convert to
# kilograms or pounds when the gram count is large.
def _normalize_quantity(quantity: float, unit: str) -> tuple[float, str]:
    u = unit.lower()
    if u == "g" and quantity >= 1000:
        return round(quantity / 1000, 2), "kg"
    if u == "ml" and quantity >= 1000:
        return round(quantity / 1000, 2), "l"
    return round(quantity, 2), u


# ---- Ingredient → human-readable product name ----
# Internal names like "queso_fresco" need to look like real grocery items.
INGREDIENT_DISPLAY = {
    "corn_tortilla":   "corn tortillas",
    "flour_tortilla":  "flour tortillas",
    "steak":           "flank steak",
    "pork":            "pork shoulder",
    "black_beans":     "black beans",
    "rice":            "long grain white rice",
    "cheese":          "shredded cheddar cheese",
    "queso_fresco":    "queso fresco",
    "onion":           "yellow onions",
    "cilantro":        "fresh cilantro",
    "pineapple":       "fresh pineapple",
    "avocado":         "Hass avocados",
    "bell_peppers":    "bell peppers",
    "jalapeno":        "jalapeño peppers",
    "salsa":           "salsa",
    "tortilla_chips":  "tortilla chips",
    "lime":            "limes",
    "coke_can":        "Coca-Cola 12oz cans",
    "lemon":           "lemons",
    "rice_milk":       "rice milk",
    "cinnamon":        "ground cinnamon",
    "sugar":           "granulated sugar",
}


def _display_name(ingredient: str) -> str:
    return INGREDIENT_DISPLAY.get(ingredient, ingredient.replace("_", " "))


# ---- Public API ----

def create_shopping_list(
    items: list[dict],
    *,
    title: str = "Food Truck Restock",
    linkback_url: Optional[str] = None,
    expires_in_days: int = 7,
) -> dict:
    """Generate an Instacart shoppable list URL.

    items: list of {"ingredient": str, "quantity": float, "unit": str}
           — typically the output of inventory.suggest_restocks().

    Returns:
        {
          "ok": True,
          "url": "https://www.instacart.com/store/recipes/...",
          "items_count": N,
          "source": "instacart_idp" | "instacart_search_fallback"
        }
        or
        {"ok": False, "error": "..."}
    """
    if not items:
        return {"ok": False, "error": "empty_items"}

    api_key = os.environ.get("INSTACART_API_KEY")

    # Build line items — happens for both the API call and the fallback URL
    line_items = []
    for item in items:
        ingredient = item["ingredient"]
        quantity, unit = _normalize_quantity(item["quantity"], item["unit"])
        line_items.append({
            "name": _display_name(ingredient),
            "quantity": quantity,
            "unit": _translate_unit(unit),
            "display_text": f"{quantity} {unit} {_display_name(ingredient)}",
        })

    # Without a key, fall back to a search URL. Demos still work.
    if not api_key:
        return _fallback_search_url(line_items)

    payload = {
        "title": title,
        "link_type": "shopping_list",
        "expires_in": expires_in_days,
        "line_items": line_items,
        "landing_page_configuration": {
            "enable_pantry_items": True,
        },
    }
    if linkback_url:
        payload["landing_page_configuration"]["partner_linkback_url"] = linkback_url

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        resp = requests.post(
            _base_url() + ENDPOINT,
            json=payload,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        # Network blip — fall back so the demo doesn't die
        fb = _fallback_search_url(line_items)
        fb["network_error"] = str(e)
        return fb

    if resp.status_code >= 400:
        # Bad key, rate limit, malformed payload. Fall back gracefully.
        fb = _fallback_search_url(line_items)
        fb["api_error"] = f"{resp.status_code}: {resp.text[:200]}"
        return fb

    data = resp.json()
    # Instacart returns {"products_link_url": "..."} or similar; both keys
    # have appeared in their docs over time, so check both.
    url = data.get("products_link_url") or data.get("url")
    if not url:
        fb = _fallback_search_url(line_items)
        fb["api_error"] = f"no url in response: {data}"
        return fb

    return {
        "ok": True,
        "url": url,
        "items_count": len(line_items),
        "source": "instacart_idp",
    }


def _fallback_search_url(line_items: list[dict]) -> dict:
    """Build a plain Instacart search URL from the first few items.

    Not a real shoppable cart, but it opens Instacart with a meaningful
    search — so the demo still ends in 'tap link → see real Instacart'.
    """
    names = [li["name"] for li in line_items[:5]]
    query = ", ".join(names)
    url = "https://www.instacart.com/store/s?k=" + urllib.parse.quote(query)
    return {
        "ok": True,
        "url": url,
        "items_count": len(line_items),
        "source": "instacart_search_fallback",
    }


# ---- Convenience: combine with your inventory module ----

def restock_link_from_low_stock() -> dict:
    """Pull current low-stock suggestions and generate an Instacart link
    for them in one call. Imports lazily so this module stays standalone."""
    from . import inventory as inv_mod

    suggestions = inv_mod.suggest_restocks()
    if not suggestions:
        return {"ok": False, "error": "no_low_stock"}

    items = [
        {
            "ingredient": s["ingredient"],
            "quantity":   s["suggested_qty"],
            "unit":       s["unit"],
        }
        for s in suggestions
    ]
    return create_shopping_list(items, title="Food Truck Restock — Low Stock Items")
