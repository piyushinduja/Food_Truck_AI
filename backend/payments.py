"""Mock payment processor.

Returns a Stripe-shaped response. To swap in real Stripe later, replace
charge() with a call to stripe.PaymentIntent.create() and keep the
return shape compatible.
"""
import uuid
import random


def charge(amount: float, customer_name: str = "guest") -> dict:
    # Simulate ~2% failure rate so the UI has to handle it
    if random.random() < 0.02:
        return {
            "status": "failed",
            "error": "card_declined",
            "amount": amount,
        }
    return {
        "status": "succeeded",
        "payment_id": f"pi_mock_{uuid.uuid4().hex[:16]}",
        "amount": round(amount, 2),
        "currency": "usd",
        "customer": customer_name,
    }
