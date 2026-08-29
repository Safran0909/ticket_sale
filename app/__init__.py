from flask import Flask

from config import Config
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import Member

    @login_manager.user_loader
    def load_user(user_id):
        return Member.query.get(int(user_id))

    from app.auth import bp as auth_bp
    from app.member import bp as member_bp
    from app.admin import bp as admin_bp
    from app.public import bp as public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    @app.context_processor
    def inject_globals():
        return {"app_name": "Committee Ticket Sales"}

    return app
