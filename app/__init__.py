import os

from flask import Flask, flash, jsonify, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
# No default limits — only the auth routes opt in via @limiter.limit.
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Render/Railway/nginx/etc. terminate HTTPS and forward plain HTTP to
    # the app — without this, Flask thinks every request is insecure, which
    # breaks SESSION_COOKIE_SECURE and generates http:// URLs. Only trust
    # these headers when actually deployed behind such a proxy, since
    # they're otherwise spoofable by the client.
    if os.environ.get("BEHIND_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    migrate.init_app(app, db)
    # Every POST/PUT/PATCH/DELETE needs a token: forms carry it as a hidden
    # field, fetch() calls get it as a header from app.js.
    csrf.init_app(app)
    limiter.init_app(app)

    @app.errorhandler(429)
    def too_many_requests(e):
        # Send people back to the form they were on with a readable message
        # instead of a bare 429 page.
        flash("Too many attempts. Please wait a minute and try again.", "error")
        return redirect(request.path)

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if request.path.startswith(("/api/", "/plaid/")):
            return jsonify({"error": "Your session expired. Reload the page and try again."}), 400
        flash("Your session expired. Please try again.", "error")
        return redirect(request.path)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.plaid_routes import plaid_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.transactions import transactions_bp
    from app.routes.categories import categories_bp
    from app.routes.security import security_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(plaid_bp, url_prefix="/plaid")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(security_bp)

    return app