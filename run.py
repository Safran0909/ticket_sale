import os
import click

from app import create_app
from app.extensions import db
from app.models import Member, TicketTier, generate_ref_code

app = create_app()


@app.cli.command("seed-admin")
@click.argument("name")
@click.argument("email")
def seed_admin(name, email):
    """Create the first admin account, e.g.:
    flask --app run.py seed-admin "Riya Kapoor" riya@example.com
    """
    email = email.strip().lower()
    if Member.query.filter_by(email=email).first():
        click.echo(f"A member with email {email} already exists.")
        return

    ref_code = generate_ref_code(name)
    member = Member(name=name, email=email, ref_code=ref_code, is_admin=True)
    db.session.add(member)
    db.session.commit()
    click.echo(f"Created admin {name} <{email}> — ref code {ref_code}")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_ENV") != "production", port=5000)
