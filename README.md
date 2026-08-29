# Committee Ticket Sales

Flask + PostgreSQL app for selling event tickets with per-committee-member
referral QR codes, PhonePe checkout, and an admin dashboard.

## How it works

1. Admin adds a committee member (name + email) → app auto-generates a
   unique referral code (e.g. `PRIYA-7F3K`) and a personal QR code.
2. Member logs in with a magic link (no password) and sees their own QR +
   share link on `/dashboard`.
3. A buyer scans the QR or opens the link → lands on `/tickets?ref=PRIYA-7F3K`
   → the ref code is remembered in their session through checkout.
4. Buyer pays via PhonePe. On success, the order is recorded against that
   ref code.
5. Members see only their own count; admins see everyone's, ticket tier
   inventory, and a 14-day sales trend chart.

## 1. Local setup

```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in the values, see below
```

Install the PhonePe SDK separately (not on plain PyPI):

```bash
pip install --index-url https://phonepe.mycloudrepo.io/public/repositories/phonepe-pg-sdk-python \
    --extra-index-url https://pypi.org/simple phonepe_sdk
```

## 2. Database

Point `DATABASE_URL` in `.env` at a Postgres instance (Railway, Render,
Supabase, Neon all have free tiers). Then:

```bash
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
```

Create your first admin account:

```bash
flask --app run.py seed-admin "Your Name" you@yourorg.com
```

## 3. Email (magic link login)

Any SMTP provider works — Gmail (with an [app password](https://myaccount.google.com/apppasswords)),
SendGrid, Resend, Postmark, etc. Fill in `SMTP_*` in `.env`. If you leave
`SMTP_HOST` blank, magic links are printed to the server console instead of
emailed — useful for local testing.

## 4. PhonePe setup

1. Register as a merchant at [business.phonepe.com/pg/register](https://business.phonepe.com/pg/register).
2. Once onboarded, grab your **Client ID**, **Client Secret**, and **Client
   Version** from the developer dashboard and put them in `.env`. Use
   `PHONEPE_ENV=SANDBOX` first to test against PhonePe's UAT environment,
   then switch to `PRODUCTION` after PhonePe approves your account.
3. In the PhonePe dashboard, configure a webhook URL pointing at
   `https://yourdomain.com/payments/webhook`, and set a **username/password**
   for it (different from your client id/secret) — put those in
   `PHONEPE_WEBHOOK_USERNAME` / `PHONEPE_WEBHOOK_PASSWORD`. This is what
   actually confirms a sale; the redirect back to your site after checkout
   is only used to show a status page, never to mark an order paid on its own.
4. Full reference: [developer.phonepe.com/payment-gateway](https://developer.phonepe.com/payment-gateway)

**Before going live**, walk through PhonePe's own UAT checklist and test at
least one full payment in SANDBOX mode end to end (checkout → webhook →
order marked PAID) before switching to PRODUCTION.

## 5. Running locally

```bash
flask --app run.py run
```

Visit `http://localhost:5000`. Log in as the admin you seeded, add a few
committee members and a ticket tier, then open `/tickets?ref=<code>` in
another tab to test the buyer flow. Payments will hit PhonePe's sandbox, so
use their [test credentials](https://developer.phonepe.com/payment-gateway/uat-testing-go-live/uat-sandbox)
to simulate a payment.

## 6. Deploying

Any host that runs a Python web process + Postgres works (Railway, Render,
Fly.io). Rough steps:

1. Push this repo to GitHub.
2. Create a Postgres database on your host, copy its connection string into
   `DATABASE_URL`.
3. Set all the other `.env` values as environment variables on the host.
4. Set the start command to: `gunicorn run:app`
5. Run `flask --app run.py db upgrade` once against the production database
   (most hosts let you run a one-off command, or add it as a release step).
6. Update `BASE_URL` to your real domain, and point PhonePe's webhook URL
   at `https://<your-domain>/payments/webhook`.

## Notes / things to double check before your event goes live

- **Referral attribution**: the ref code is stored in the buyer's session
  when they open the link, and stays there through checkout even if they
  browse the ticket page a bit first. It's cleared after checkout completes.
- **Overselling protection**: `remaining` inventory is checked at checkout
  time, but under high concurrency two buyers could still both pass the
  check for the last ticket before either one's order is confirmed. Fine for
  a committee-scale sale; if you expect a rush, consider a `SELECT ... FOR
  UPDATE` lock around the inventory check.
- **Refunds**: this app doesn't include a refund flow. PhonePe's SDK
  supports refunds (`client.refund(...)`) if you need to add one later.
- **Admin promotion**: the first account is admin via `seed-admin`. To make
  another member an admin from the database directly:
  `UPDATE members SET is_admin = true WHERE email = '...';`
