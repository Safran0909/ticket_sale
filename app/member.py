from flask import Blueprint, render_template, url_for, Response, current_app
from flask_login import login_required, current_user

from app.utils.qr import generate_qr_png_bytes

bp = Blueprint("member", __name__)


def _purchase_link(ref_code: str) -> str:
    base = current_app.config["BASE_URL"].rstrip("/")
    return f"{base}{url_for('public.buy_tickets')}?ref={ref_code}"


@bp.route("/dashboard")
@login_required
def dashboard():
    link = _purchase_link(current_user.ref_code)
    return render_template("member_dashboard.html", member=current_user, purchase_link=link)


@bp.route("/dashboard/qr.png")
@login_required
def qr_code():
    link = _purchase_link(current_user.ref_code)
    png_bytes = generate_qr_png_bytes(link)
    return Response(png_bytes, mimetype="image/png")
