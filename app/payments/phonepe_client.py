"""
Thin wrapper around PhonePe's official Python SDK (Standard Checkout, v2 API).
Method signatures below are verified against PhonePe's developer docs as of
Aug 2026 — re-check https://developer.phonepe.com/payment-gateway/backend-sdk/python-be-sdk/
if PhonePe changes the SDK.

Install the SDK separately (it's not on plain PyPI):

    pip install --index-url https://phonepe.mycloudrepo.io/public/repositories/phonepe-pg-sdk-python \
        --extra-index-url https://pypi.org/simple phonepe_sdk

Flow used by this app:
  1. initiate_payment() -> creates a PhonePe order, returns a checkout URL
  2. buyer is redirected to that URL, pays, PhonePe redirects back to /payments/return
  3. PhonePe also POSTs a webhook to /payments/webhook (server-to-server,
     this is the source of truth — the redirect alone is NOT proof of payment)
  4. check_order_status() is used as a fallback if the webhook hasn't arrived yet
"""

from flask import current_app

_client = None  # cached singleton — the SDK raises if you re-init with new creds


def _get_client():
    """Lazily import + construct the SDK client so the app can still boot
    (e.g. for local dev without the SDK installed) until payments are used."""
    global _client
    if _client is not None:
        return _client

    from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
    from phonepe.sdk.pg.env import Env

    cfg = current_app.config
    env = Env.PRODUCTION if cfg["PHONEPE_ENV"] == "PRODUCTION" else Env.SANDBOX

    _client = StandardCheckoutClient.get_instance(
        client_id=cfg["PHONEPE_CLIENT_ID"],
        client_secret=cfg["PHONEPE_CLIENT_SECRET"],
        client_version=cfg["PHONEPE_CLIENT_VERSION"],
        env=env,
    )
    return _client


def initiate_payment(merchant_order_id: str, amount_rupees: int, redirect_url: str, ref_code: str = "") -> str:
    """Create a PhonePe order and return the checkout page URL to redirect the buyer to.

    ref_code (the committee member's referral code) is passed through in
    metaInfo.udf1 so it comes back unchanged on the webhook/status response —
    useful as a belt-and-braces cross-check against what we stored in our own
    Order row.
    """
    from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import (
        StandardCheckoutPayRequest,
    )
    from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo

    client = _get_client()
    meta_info = MetaInfo(udf1=ref_code or "none")

    request = StandardCheckoutPayRequest.build_request(
        merchant_order_id=merchant_order_id,
        amount=amount_rupees * 100,  # PhonePe amounts are in paise, minimum 100 paise
        redirect_url=redirect_url,
        meta_info=meta_info,
        expire_after=1800,  # 30 min checkout window
    )
    response = client.pay(request)
    return response.redirect_url


def check_order_status(merchant_order_id: str) -> str:
    """Returns PhonePe's order state, e.g. 'COMPLETED', 'FAILED', 'PENDING'."""
    client = _get_client()
    response = client.get_order_status(merchant_order_id=merchant_order_id)
    return response.state


def verify_webhook(username: str, password: str, authorization_header: str, response_body: str):
    """Validates an inbound PhonePe webhook using the SHA-256 auth header scheme.

    `username`/`password` are the credentials YOU configure in the PhonePe
    dashboard for webhook auth (not your client id/secret) — set them as
    PHONEPE_WEBHOOK_USERNAME / PHONEPE_WEBHOOK_PASSWORD.
    Returns a CallbackResponse (`.type`, `.payload.state`, `.payload.original_merchant_order_id`, ...).
    Raises PhonePeException if the signature doesn't match — treat that as a
    rejected/ignored webhook, never trust an unverified body.
    """
    client = _get_client()
    return client.validate_callback(
        username=username,
        password=password,
        callback_header_data=authorization_header,
        callback_response_data=response_body,
    )
