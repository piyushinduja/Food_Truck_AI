"""Menu timing estimates derived from item type and preparation signals."""
from __future__ import annotations

from collections.abc import Iterable


def estimate_menu_timing(item: dict, ingredients: Iterable[str] | None = None) -> tuple[float, float]:
    """Return reasonable prep/cook minutes for a menu item.

    The estimator is intentionally deterministic: category and text describe the
    baseline station work, while ingredients nudge items that need grilling,
    assembly, or only handoff.
    """
    category = str(item.get("category") or "").lower()
    name = str(item.get("name") or "").lower()
    description = str(item.get("description") or "").lower()
    text = f"{name} {description}"
    ingredient_text = " ".join(str(i).lower() for i in (ingredients or ()))

    if category == "drinks" or any(word in text for word in ("coke", "lemonade", "horchata")):
        if any(word in text for word in ("can", "bottle", "coke")):
            return 0.2, 0.0
        if any(word in text for word in ("fresh", "squeezed", "lemonade")):
            return 1.3, 0.0
        if "horchata" in text or "rice milk" in text:
            return 0.7, 0.0
        return 0.5, 0.0

    if "guacamole" in text:
        return 2.2, 0.0
    if "nachos" in text:
        return 1.5, 3.2

    grill_weight = 0.0
    if any(word in text or word in ingredient_text for word in ("steak", "carne", "asada")):
        grill_weight += 1.1
    if any(word in text or word in ingredient_text for word in ("pork", "pastor")):
        grill_weight += 0.8
    if any(word in text or word in ingredient_text for word in ("pepper", "veggie", "beans")):
        grill_weight += 0.4

    if category == "burritos" or "burrito" in text:
        return round(2.4 + min(grill_weight, 1.1) * 0.3, 1), round(4.8 + grill_weight, 1)
    if category == "tacos" or "taco" in text:
        return round(1.1 + min(grill_weight, 1.0) * 0.2, 1), round(2.6 + grill_weight, 1)
    if category == "sides":
        return 1.4, 2.0

    return 1.0, 3.0


def has_placeholder_timing(item: dict) -> bool:
    """Detect legacy placeholder timing that should be replaced."""
    try:
        prep = float(item.get("prep_time_minutes") or 0)
        cook = float(item.get("cook_time_minutes") or 0)
    except (TypeError, ValueError):
        return True
    return (prep, cook) in {(1.0, 5.0), (1.0, 0.0), (0.0, 5.0), (0.0, 0.0)}
