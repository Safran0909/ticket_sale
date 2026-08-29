import uuid

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, session,
)

from app.extensions import db, csrf
from app.models import Member, TicketTier, Order
from app.payments import phonepe_client

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    return redirect(url_for("public.buy_tickets"))


@bp.route("/tickets", methods=["GET"])
def buy_tickets():
    ref = request.args.get("ref", "").strip().upper()
    if ref:
        # Only remember the ref if it belongs to a real, active member —
        # otherwise silently drop it rather than attributing to a bad code.
        member = Member.query.filter_by(ref_code=ref, is_active_member=True).first()
        if member:
            session["ref_code"] = ref

    tiers = TicketTier.query.filter_by(is_active=True).order_by(TicketTier.price_inr).all()
    return render_template("buy_tickets.html", tiers=tiers, ref_code=session.get("ref_code"))


@bp.route("/tickets/checkout", methods=["POST"])
def checkout():
    tier = TicketTier.query.get_or_404(int(request.form["tier_id"]))
    quantity = max(1, min(10, int(request.form.get("quantity", 1))))

    if tier.remaining < quantity:
        flash(f"Sorry, only {tier.remaining} '{tier.name}' tickets left.", "error")
        return redirect(url_for("public.buy_tickets"))

    buyer_name = request.form.get("buyer_name", "").strip()
    buyer_email = request.form.get("buyer_email", "").strip().lower()
    buyer_phone = request.form.get("buyer_phone", "").strip()

    if not (buyer_name and buyer_email and buyer_phone):
        flash("Please fill in your name, email, and phone number.", "error")
        return redirect(url_for("public.buy_tickets"))

    ref_code = session.get("ref_code", "")
    amount = tier.price_inr * quantity
    merchant_order_id = f"TIX-{uuid.uuid4().hex[:20]}"

    order = Order(
        merchant_order_id=merchant_order_id,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        buyer_phone=buyer_phone,
        tier_id=tier.id,
        quantity=quantity,
        amount=amount,
        ref_code=ref_code or None,
        status="PENDING",
    )
    db.session.add(order)
    db.session.commit()

    redirect_url = url_for("public.payment_return", order_id=merchant_order_id, _external=True)

    try:
        checkout_url = phonepe_client.initiate_payment(
            merchant_order_id=merchant_order_id,
            amount_rupees=amount,
            redirect_url=redirect_url,
            ref_code=ref_code,
        )
    except Exception as exc:  # noqa: BLE001 — surface any PhonePe/SDK error to the buyer
        current_app.logger.exception("PhonePe initiate_payment failed for %s", merchant_order_id)
        order.status = "FAILED"
        db.session.commit()
        flash("We couldn't start the payment. Please try again in a moment.", "error")
        return redirect(url_for("public.buy_tickets"))

    return redirect(checkout_url)


@bp.route("/payments/return")
def payment_return():
    """Buyer lands here after PhonePe checkout. This is NOT proof of payment —
    it's just where we show a status page. The webhook (or a status check
    here as a fallback) is what actually confirms and records the sale."""
    merchant_order_id = request.args.get("order_id", "")
    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order is None:
        flash("We couldn't find that order.", "error")
        return redirect(url_for("public.buy_tickets"))

    if order.status == "PENDING":
        try:
            state = phonepe_client.check_order_status(merchant_order_id)
            if state == "COMPLETED":
                order.status = "PAID"
            elif state in ("FAILED", "EXPIRED"):
                order.status = state
            db.session.commit()
        except Exception:  # noqa: BLE001
            current_app.logger.exception("Order status check failed for %s", merchant_order_id)

    session.pop("ref_code", None)
    return render_template("payment_status.html", order=order)


@bp.route("/payments/webhook", methods=["POST"])
@csrf.exempt  # server-to-server call from PhonePe — verified via signature instead, see verify_webhook()
def payment_webhook():
    """Server-to-server callback from PhonePe — the source of truth for
    payment status. Must return 200 quickly; PhonePe retries on failure."""
    auth_header = request.headers.get("Authorization", "")
    body = request.get_data(as_text=True)

    cfg = current_app.config
    try:
        callback = phonepe_client.verify_webhook(
            username=cfg["PHONEPE_WEBHOOK_USERNAME"],
            password=cfg["PHONEPE_WEBHOOK_PASSWORD"],
            authorization_header=auth_header,
            response_body=body,
        )
    except Exception:  # noqa: BLE001 — invalid signature or malformed payload
        current_app.logger.warning("Rejected an unverifiable PhonePe webhook")
        return "invalid signature", 400

    payload = callback.payload
    merchant_order_id = getattr(payload, "original_merchant_order_id", None) or getattr(
        payload, "originalMerchantOrderId", None
    )
    state = getattr(payload, "state", None)

    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order is None:
        current_app.logger.warning("Webhook for unknown order %s", merchant_order_id)
        return "ok", 200  # acknowledge anyway so PhonePe stops retrying

    if state == "COMPLETED":
        order.status = "PAID"
        order.phonepe_transaction_id = getattr(payload, "orderId", None) or getattr(payload, "order_id", None)
    elif state in ("FAILED", "EXPIRED"):
        order.status = state

    db.session.commit()
    return "ok", 200
