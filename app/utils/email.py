import resend
from flask import current_app


def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    api_key = current_app.config.get("RESEND_API_KEY")
    from_email = current_app.config.get("EMAIL_FROM")

    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")

    if not from_email:
        raise RuntimeError("EMAIL_FROM is not configured")

    resend.api_key = api_key

    params = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }

    if text_body:
        params["text"] = text_body

    try:
        email = resend.Emails.send(params)
        current_app.logger.info(
            "Email sent successfully to %s: %s",
            to_email,
            email
        )
        return email

    except Exception:
        current_app.logger.exception(
            "Failed to send email to %s",
            to_email
        )
        raise


def send_magic_link_email(to_email: str, name: str, link: str):
    subject = "Your login link"

    html = f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
      <h2 style="color:#1a1a2e;">Hi {name},</h2>

      <p>
        Click the button below to log in. This link expires in 15 minutes
        and can only be used once.
      </p>

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

    text = f"""
Hi {name},

Click this link to log in:

{link}

This link expires in 15 minutes and can only be used once.

If you didn't request this, you can safely ignore this email.
"""

    return send_email(to_email, subject, html, text)


def send_ticket_confirmation_email(to_email: str, buyer_name: str, tier_name: str, quantity: int, amount: int, merchant_order_id: str):
    subject = "Your ticket is confirmed!"

    html = f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
      <h2 style="color:#1a1a2e;">You're in, {buyer_name}! 🎉</h2>

      <p>Your ticket purchase is confirmed. Here are the details:</p>

      <table style="width:100%; border-collapse: collapse; margin: 24px 0;">
        <tr>
          <td style="padding:8px 0; color:#888;">Order</td>
          <td style="padding:8px 0; text-align:right;"><strong>{merchant_order_id}</strong></td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#888;">Ticket</td>
          <td style="padding:8px 0; text-align:right;">{quantity} × {tier_name}</td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#888;">Amount paid</td>
          <td style="padding:8px 0; text-align:right;"><strong>₹{amount}</strong></td>
        </tr>
      </table>

      <p style="color:#888; font-size:13px;">
        Keep this email as your confirmation. See you there!
      </p>
    </div>
    """

    text = f"""
You're in, {buyer_name}!

Order: {merchant_order_id}
Ticket: {quantity} x {tier_name}
Amount paid: Rs {amount}

Keep this email as your confirmation. See you there!
"""

    return send_email(to_email, subject, html, text)