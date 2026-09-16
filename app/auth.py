import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import BadSignature, SignatureExpired

from app.extensions import db
from app.models import Member, MagicLinkToken, get_serializer, utcnow
from app.utils.email import send_magic_link_email

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("member.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        member = Member.query.filter_by(email=email).first()

        # Always show the same message whether or not the account exists,
        # so this can't be used to enumerate committee member emails.
        if member and member.is_active_member:
            jti = secrets.token_urlsafe(16)
            token_record = MagicLinkToken(member_id=member.id, jti=jti)
            db.session.add(token_record)
            db.session.commit()

            serializer = get_serializer(current_app.config["SECRET_KEY"])
            token = serializer.dumps({"member_id": member.id, "jti": jti})
            link = url_for("auth.verify", token=token, _external=True)

            try:
                send_magic_link_email(member.email, member.name, link)
                current_app.logger.info("Magic link email sent to %s", member.email)
            except Exception:
                current_app.logger.exception("MAGIC LINK EMAIL FAILED")
                raise

        flash("If that email is registered, a login link has been sent. Check your inbox.", "info")
        return redirect(url_for("auth.login"))

    return render_template("login.html")


@bp.route("/login/verify")
def verify():
    token = request.args.get("token", "")
    serializer = get_serializer(current_app.config["SECRET_KEY"])

    try:
        data = serializer.loads(token, max_age=current_app.config["MAGIC_LINK_MAX_AGE"])
    except SignatureExpired:
        flash("That login link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("That login link is invalid.", "error")
        return redirect(url_for("auth.login"))

    token_record = MagicLinkToken.query.filter_by(jti=data["jti"]).first()
    if token_record is None or token_record.used_at is not None:
        flash("That login link has already been used. Please request a new one.", "error")
        return redirect(url_for("auth.login"))

    token_record.used_at = utcnow()
    db.session.commit()

    member = Member.query.get(data["member_id"])
    if member is None or not member.is_active_member:
        flash("This account is no longer active.", "error")
        return redirect(url_for("auth.login"))

    login_user(member)
    flash(f"Welcome back, {member.name.split(' ')[0]}!", "success")

    if member.is_admin:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("member.dashboard"))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))
