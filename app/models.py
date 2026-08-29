import secrets
import string
from datetime import datetime, timezone

from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def generate_ref_code(name: str) -> str:
    """e.g. 'Priya Sharma' -> 'PRIYA-7F3K' (unique, human-readable)."""
    base = "".join(ch for ch in name.upper().split(" ")[0] if ch.isalnum()) or "MEMBER"
    base = base[:10]
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{base}-{suffix}"


class Member(UserMixin, db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    ref_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active_member = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    orders = db.relationship("Order", backref="sold_by", lazy="dynamic")

    def get_id(self):
        return str(self.id)

    @property
    def total_tickets_sold(self):
        return sum(o.quantity for o in self.orders if o.status == "PAID")

    @property
    def total_revenue(self):
        return sum(o.amount for o in self.orders if o.status == "PAID")

    def __repr__(self):
        return f"<Member {self.email} ref={self.ref_code}>"


class MagicLinkToken(db.Model):
    """
    We don't actually store the token itself (it's a signed itsdangerous
    token containing the member id + purpose), but we keep a record so a
    link can only be used once and admins can audit login activity.
    """

    __tablename__ = "magic_link_tokens"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    jti = db.Column(db.String(64), unique=True, nullable=False)  # random id embedded in the token
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    member = db.relationship("Member")


class TicketTier(db.Model):
    __tablename__ = "ticket_tiers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # e.g. "General", "VIP"
    description = db.Column(db.String(500))
    price_inr = db.Column(db.Integer, nullable=False)  # store in whole rupees
    total_inventory = db.Column(db.Integer, nullable=False)  # total tickets available
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    orders = db.relationship("Order", backref="tier", lazy="dynamic")

    @property
    def sold_count(self):
        return sum(o.quantity for o in self.orders if o.status == "PAID")

    @property
    def remaining(self):
        return max(self.total_inventory - self.sold_count, 0)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    merchant_order_id = db.Column(db.String(64), unique=True, nullable=False, index=True)

    buyer_name = db.Column(db.String(120), nullable=False)
    buyer_email = db.Column(db.String(255), nullable=False)
    buyer_phone = db.Column(db.String(20), nullable=False)

    tier_id = db.Column(db.Integer, db.ForeignKey("ticket_tiers.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    amount = db.Column(db.Integer, nullable=False)  # total paise->rupees, whole rupees

    ref_code = db.Column(db.String(32), db.ForeignKey("members.ref_code"), nullable=True, index=True)

    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)
    # PENDING, PAID, FAILED, EXPIRED

    phonepe_transaction_id = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<Order {self.merchant_order_id} {self.status}>"


def get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="magic-link")
