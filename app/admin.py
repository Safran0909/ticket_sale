from datetime import timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import current_user

from app.extensions import db
from app.models import Member, TicketTier, Order, generate_ref_code, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def _guard():
    """Applies admin-only access to every route in this blueprint."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.is_admin:
        abort(403)


@bp.route("/")
def dashboard():
    members = Member.query.order_by(Member.name).all()
    tiers = TicketTier.query.order_by(TicketTier.created_at).all()

    total_tickets = sum(m.total_tickets_sold for m in members)
    total_revenue = sum(m.total_revenue for m in members)

    leaderboard = sorted(members, key=lambda m: m.total_tickets_sold, reverse=True)

    return render_template(
        "admin_dashboard.html",
        members=members,
        tiers=tiers,
        total_tickets=total_tickets,
        total_revenue=total_revenue,
        leaderboard=leaderboard,
    )


@bp.route("/sales-trend.json")
def sales_trend():
    """Last 14 days of paid ticket sales, grouped by day — feeds the trend chart."""
    since = utcnow() - timedelta(days=14)
    orders = Order.query.filter(Order.status == "PAID", Order.created_at >= since).all()

    by_day = {}
    for o in orders:
        day = o.created_at.strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + o.quantity

    labels = sorted(by_day.keys())
    return jsonify({"labels": labels, "values": [by_day[d] for d in labels]})


# ---------- Members ----------

@bp.route("/members/new", methods=["POST"])
def create_member():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()

    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("admin.dashboard"))

    if Member.query.filter_by(email=email).first():
        flash(f"A member with email {email} already exists.", "error")
        return redirect(url_for("admin.dashboard"))

    ref_code = generate_ref_code(name)
    while Member.query.filter_by(ref_code=ref_code).first():
        ref_code = generate_ref_code(name)

    member = Member(name=name, email=email, ref_code=ref_code)
    db.session.add(member)
    db.session.commit()

    flash(f"Added {name} with referral code {ref_code}.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/members/<int:member_id>/toggle-active", methods=["POST"])
def toggle_member_active(member_id):
    member = Member.query.get_or_404(member_id)
    member.is_active_member = not member.is_active_member
    db.session.commit()
    state = "reactivated" if member.is_active_member else "deactivated"
    flash(f"{member.name} was {state}.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.route("/members/<int:member_id>/make-admin", methods=["POST"])
def make_admin(member_id):
    member = Member.query.get_or_404(member_id)
    member.is_admin = True
    db.session.commit()
    flash(f"{member.name} is now an admin.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------- Ticket tiers / inventory ----------

@bp.route("/tiers/new", methods=["POST"])
def create_tier():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    try:
        price = int(request.form.get("price_inr", 0))
        inventory = int(request.form.get("total_inventory", 0))
    except ValueError:
        flash("Price and inventory must be whole numbers.", "error")
        return redirect(url_for("admin.dashboard"))

    if not name or price <= 0 or inventory <= 0:
        flash("Please fill in a valid name, price, and inventory.", "error")
        return redirect(url_for("admin.dashboard"))

    tier = TicketTier(name=name, description=description, price_inr=price, total_inventory=inventory)
    db.session.add(tier)
    db.session.commit()

    flash(f"Added ticket tier '{name}'.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/tiers/<int:tier_id>/toggle-active", methods=["POST"])
def toggle_tier_active(tier_id):
    tier = TicketTier.query.get_or_404(tier_id)
    tier.is_active = not tier.is_active
    db.session.commit()
    state = "enabled" if tier.is_active else "disabled"
    flash(f"'{tier.name}' is now {state} for sale.", "info")
    return redirect(url_for("admin.dashboard"))
