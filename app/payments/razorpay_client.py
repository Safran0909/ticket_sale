"""
Thin wrapper around Razorpay's Orders API + Checkout.js — the flow used by
buy_tickets.html's in-page payment modal.

Flow:
  1. create_order() -> creates a Razorpay Order, returned to the frontend
     so Checkout.js can open its payment modal
  2. buyer pays in the modal; Razorpay's JS `handler` callback fires with
     razorpay_order_id/razorpay_payment_id/razorpay_signature
  3. verify_payment_signature() checks that signature server-side before
     we ever mark an order PAID — never trust the JS callback alone
  4. Razorpay also POSTs a webhook to /payments/webhook independently —
     the belt-and-braces source of truth if the buyer closes their
     browser before the JS callback completes
"""

from flask import current_app

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    import razorpay

    cfg = current_app.config
    _client = razorpay.Client(auth=(cfg["RAZORPAY_KEY_ID"], cfg["RAZORPAY_KEY_SECRET"]))
    return _client


def create_order(merchant_order_id: str, amount_rupees: int, ref_code: str = "") -> dict:
    """Create a Razorpay Order and return the raw response dict (id, amount, currency, ...).

    notes.merchant_order_id lets us match this back to our own Order row
    later, from both the JS callback and the webhook payload.
    """
    client = _get_client()
    return client.order.create({
        "amount": amount_rupees * 100,  # Razorpay amounts are in paise
        "currency": "INR",
        "receipt": merchant_order_id,
        "notes": {"merchant_order_id": merchant_order_id, "ref_code": ref_code or "none"},
    })


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> None:
    """Raises razorpay.errors.SignatureVerificationError on a bad signature —
    treat that as unverified, never trust the raw callback params."""
    client = _get_client()
    client.utility.verify_payment_signature({
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    })


def verify_webhook(body: str, signature: str) -> dict:
    """Validates an inbound Razorpay webhook using RAZORPAY_WEBHOOK_SECRET
    (set separately in the Razorpay dashboard under Settings > Webhooks).

    Raises razorpay.errors.SignatureVerificationError on a bad signature.
    Returns the parsed JSON payload dict on success.
    """
    import json

    client = _get_client()
    client.utility.verify_webhook_signature(
        body, signature, current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    )
    return json.loads(body)