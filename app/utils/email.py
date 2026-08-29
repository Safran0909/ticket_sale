import smtplib
from email.mime.text import MIMEText
from flask import current_app


def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    """Send an email via SMTP using settings from Config. Raises on failure
    so callers can show an error instead of silently losing the email."""
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        current_app.logger.warning(
            "SMTP not configured — printing email to console instead:\n%s\n%s",
            subject,
            html_body,
        )
        return

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = to_email

    with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
        server.starttls()
        server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
        server.sendmail(cfg["SMTP_FROM"], [to_email], msg.as_string())


def send_magic_link_email(to_email: str, name: str, link: str):
    subject = "Your login link"
    html = f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
      <h2 style="color:#1a1a2e;">Hi {name},</h2>
      <p>Click the button below to log in. This link expires in 15 minutes
      and can only be used once.</p>
      <p style="text-align:center; margin: 32px 0;">
        <a href="{link}"
           style="background:#c9a227; color:#1a1a2e; padding:14px 28px;
                  text-decoration:none; border-radius:6px; font-weight:bold;
                  display:inline-block;">
          Log in
        </a>
      </p>
      <p style="color:#888; font-size:13px;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """
    send_email(to_email, subject, html)
