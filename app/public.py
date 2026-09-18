import uuid
from app.utils.email import send_ticket_confirmation_email

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, session, jsonify,
)

from app.extensions import db, csrf
from app.models import Member, TicketTier, Order
from app.payments import razorpay_client
import razorpay as razorpay_sdk

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    return redirect(url_for("public.buy_tickets"))


@bp.route("/tickets", methods=["GET"])
def buy_tickets():
    ref = request.args.get("ref", "").strip().upper()
    if ref:
        member = Member.query.filter_by(ref_code=ref, is_active_member=True).first()
        if member:
            session["ref_code"] = ref

    tiers = TicketTier.query.filter_by(is_active=True).order_by(TicketTier.price_inr).all()
    return render_template("buy_tickets.html", tiers=tiers, ref_code=session.get("ref_code"))


@bp.route("/tickets/create-order", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}

    try:
        tier_id = int(data.get("tier_id"))
        quantity = max(1, min(10, int(data.get("quantity", 1))))
    except (TypeError, ValueError):
        return jsonify(error="Invalid ticket selection."), 400

    tier = TicketTier.query.get(tier_id)
    if tier is None or not tier.is_active:
        return jsonify(error="That ticket tier isn't available."), 400
    if tier.remaining < quantity:
        return jsonify(error=f"Sorry, only {tier.remaining} '{tier.name}' tickets left."), 400

    buyer_name = (data.get("buyer_name") or "").strip()
    buyer_email = (data.get("buyer_email") or "").strip().lower()
    buyer_phone = (data.get("buyer_phone") or "").strip()
    if not (buyer_name and buyer_email and buyer_phone):
        return jsonify(error="Please fill in your name, email, and phone number."), 400

    ref_code = session.get("ref_code", "")
    amount_rupees = tier.price_inr * quantity
    merchant_order_id = f"TIX-{uuid.uuid4().hex[:20]}"

    order = Order(
        merchant_order_id=merchant_order_id,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        buyer_phone=buyer_phone,
        tier_id=tier.id,
        quantity=quantity,
        amount=amount_rupees,
        ref_code=ref_code or None,
        status="PENDING",
    )
    db.session.add(order)
    db.session.commit()

    try:
        rp_order = razorpay_client.create_order(merchant_order_id, amount_rupees, ref_code)
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Razorpay order.create failed for %s", merchant_order_id)
        order.status = "FAILED"
        db.session.commit()
        return jsonify(error="We couldn't start the payment. Please try again in a moment."), 502
    order.razorpay_order_id = rp_order["id"]
    db.session.commit()

    return jsonify(
        key_id=current_app.config["RAZORPAY_KEY_ID"],
        amount=rp_order["amount"],
        currency=rp_order["currency"],
        order_id=rp_order["id"],
        merchant_order_id=merchant_order_id,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        buyer_phone=buyer_phone,
    )


@bp.route("/tickets/verify-payment", methods=["POST"])
def verify_payment():
    data = request.get_json(silent=True) or {}
    merchant_order_id = data.get("merchant_order_id", "")

    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order is None:
        return jsonify(error="We couldn't find that order."), 404

    submitted_order_id = data.get("razorpay_order_id", "")
    if submitted_order_id != order.razorpay_order_id:
        current_app.logger.warning("Order ID mismatch for %s", merchant_order_id)
        return jsonify(error="Payment does not match this order."), 400

    try:
        razorpay_client.verify_payment_signature(
            data.get("razorpay_order_id", ""),
            data.get("razorpay_payment_id", ""),
            data.get("razorpay_signature", ""),
        )
    except razorpay_sdk.errors.SignatureVerificationError:
        current_app.logger.warning("Bad payment signature for %s", merchant_order_id)
        return jsonify(error="We couldn't verify your payment. Please contact support."), 400
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Verification error for %s", merchant_order_id)
        return jsonify(error="Something went wrong verifying your payment."), 502

    # ---- NEW: only send the email once, whichever path (webhook or here) gets there first ----
    was_already_paid = order.status == "PAID"
    order.status = "PAID"
    order.payment_transaction_id = data.get("razorpay_payment_id", "")
    db.session.commit()
    session.pop("ref_code", None)

    if not was_already_paid:
        try:
            send_ticket_confirmation_email(
                to_email=order.buyer_email,
                buyer_name=order.buyer_name,
                tier_name=order.tier.name,
                quantity=order.quantity,
                amount=order.amount,
                merchant_order_id=order.merchant_order_id,
            )
        except Exception:  # noqa: BLE001
            current_app.logger.exception("Failed to send confirmation email for %s", merchant_order_id)
    # -----------------------------------------------------------------------------------------

    return jsonify(
        status="success",
        redirect=url_for("public.payment_return", order_id=merchant_order_id),
    )

@bp.route("/payments/return")
def payment_return():
    """Buyer lands here after verify_payment already confirmed the
    signature and updated the order — this route just shows the result."""
    merchant_order_id = request.args.get("order_id", "")
    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order is None:
        flash("We couldn't find that order.", "error")
        return redirect(url_for("public.buy_tickets"))

    return render_template("payment_status.html", order=order)


@bp.route("/payments/webhook", methods=["POST"])
@csrf.exempt  # server-to-server call from Razorpay — verified via signature instead
def payment_webhook():
    """Independent backup: confirms PAID status even if the buyer's
    browser never returns to /payments/return."""
    signature = request.headers.get("X-Razorpay-Signature", "")
    body = request.get_data(as_text=True)

    try:
        event = razorpay_client.verify_webhook(body, signature)
    except razorpay_sdk.errors.SignatureVerificationError:
        current_app.logger.warning("Rejected an unverifiable Razorpay webhook")
        return "invalid signature", 400
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Malformed Razorpay webhook payload")
        return "bad payload", 400

    event_type = event.get("event", "")
    payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    merchant_order_id = payment_entity.get("notes", {}).get("merchant_order_id")
    payment_id = payment_entity.get("id")

    if not merchant_order_id:
        current_app.logger.warning("Webhook with no merchant_order_id, event=%s", event_type)
        return "ok", 200

    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order is None:
        current_app.logger.warning("Webhook for unknown order %s", merchant_order_id)
        return "ok", 200

    if event_type in ("payment.captured", "order.paid"):
        was_already_paid = order.status == "PAID"
        order.status = "PAID"
        order.payment_transaction_id = payment_id

        if not was_already_paid:
            try:
                send_ticket_confirmation_email(
                    to_email=order.buyer_email,
                    buyer_name=order.buyer_name,
                    tier_name=order.tier.name,
                    quantity=order.quantity,
                    amount=order.amount,
                    merchant_order_id=order.merchant_order_id,
                )
            except Exception:  # noqa: BLE001
                current_app.logger.exception("Failed to send confirmation email for %s", merchant_order_id)
    elif event_type == "payment.failed":
        order.status = "FAILED"

    db.session.commit()
    return "ok", 200