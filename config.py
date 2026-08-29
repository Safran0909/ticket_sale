import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///dev.db"
    ).replace("postgres://", "postgresql://", 1)  # Heroku/Railway compat
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Only send the session cookie over HTTPS, and never on cross-site requests.
    # Defaults to off so http://localhost testing still works — set
    # SESSION_COOKIE_SECURE=true in .env once you deploy behind real HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True

    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

    PHONEPE_CLIENT_ID = os.environ.get("PHONEPE_CLIENT_ID")
    PHONEPE_CLIENT_SECRET = os.environ.get("PHONEPE_CLIENT_SECRET")
    PHONEPE_CLIENT_VERSION = int(os.environ.get("PHONEPE_CLIENT_VERSION", 1))
    PHONEPE_ENV = os.environ.get("PHONEPE_ENV", "SANDBOX")  # SANDBOX | PRODUCTION
    PHONEPE_WEBHOOK_USERNAME = os.environ.get("PHONEPE_WEBHOOK_USERNAME")
    PHONEPE_WEBHOOK_PASSWORD = os.environ.get("PHONEPE_WEBHOOK_PASSWORD")

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").lower().strip()

    # Magic link tokens expire after 15 minutes
    MAGIC_LINK_MAX_AGE = 15 * 60
