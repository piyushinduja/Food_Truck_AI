"""AI Daily Brief — collects all business data and sends to Groq for a morning summary."""
import json
import os
from groq import Groq

from . import analytics, inventory as inv_mod

TEXT_MODEL = "llama-3.3-70b-versatile"

BRIEF_SYSTEM = """You are a sharp business analyst for a food truck called El Camino.

You receive structured JSON with today's operations data. Write a concise morning brief in markdown.

Format:
## [One punchy headline about today's situation]

**Performance**
- [Bullet on today's revenue vs recent average]
- [Bullet on order volume / avg ticket]
- [Bullet on best or worst trend from the week]

**Top Sellers (7 days)**
| Item | Units | Revenue |
|------|-------|---------|
[Top 3 rows]

**Stock Risks**
[If any low-stock items: list them with urgency. If none, say "✓ All clear."]

**Action Item**
> [One specific, concrete thing the owner should do today. Be direct and numbers-based.]

Rules:
- Be direct — the owner is busy
- Use real numbers from the data
- Don't invent data not in the JSON
- Keep total length under 300 words
"""


def generate_daily_brief() -> str:
    """Collect all business data and return an LLM-generated markdown brief."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")

    # Gather all available data
    data = {
        "today": analytics.today_summary(),
        "sales_today": analytics.sales_by_item(days=1),
        "sales_7d": analytics.sales_by_item(days=7),
        "revenue_7d": analytics.revenue_by_day(days=7),
        "revenue_by_category_7d": analytics.revenue_by_category(days=7),
        "low_stock": inv_mod.get_low_stock(),
        "restock_suggestions": inv_mod.suggest_restocks(),
    }

    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": BRIEF_SYSTEM},
            {"role": "user", "content": json.dumps(data, default=str)},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content or "Brief generation failed — no content returned."
