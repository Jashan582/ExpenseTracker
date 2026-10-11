import time

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from app import db, limiter, mfa
from app.models import User, Tenant, Category

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 12
# How long someone has to enter their authenticator code after a correct password.
MFA_PENDING_SECONDS = 300

DEFAULT_CATEGORIES = [
    ("Groceries", "#3C6E5D"),
    ("Dining Out", "#C68B3D"),
    ("Transportation", "#5B7A99"),
    ("Housing", "#14242C"),
    ("Subscriptions", "#8B5E83"),
    ("Shopping", "#A6483A"),
    ("Health", "#4E8B7D"),
    ("Uncategorized", "#9A9A92"),
]


def _form_email():
    return request.form.get("email", "").strip().lower()


def _pending_mfa_user_id():
    return str((session.get("mfa_pending") or {}).get("user_id", ""))


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def signup():
    if request.method == "POST":
        business_name = request.form["business_name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
            return redirect(url_for("auth.signup"))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return redirect(url_for("auth.signup"))

        slug = business_name.lower().replace(" ", "-")
        tenant = Tenant(name=business_name, slug=slug)
        db.session.add(tenant)
        db.session.flush()  # get tenant.id before commit

        for name, color in DEFAULT_CATEGORIES:
            db.session.add(Category(tenant_id=tenant.id, name=name, color=color, is_default=True))

        user = User(tenant_id=tenant.id, email=email, display_name=business_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard.index"))

    return render_template("signup.html", min_password_length=MIN_PASSWORD_LENGTH)


@auth_bp.route("/login", methods=["GET", "POST"])
# Per IP stops one machine hammering many accounts; per email stops a
# botnet hammering one account.
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("5 per minute;20 per hour", key_func=_form_email, methods=["POST"])
def login():
    if request.method == "POST":
        email = _form_email()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.mfa_enabled:
                # Password alone isn't enough — hold the user here until
                # they pass the code step in login_verify().
                session["mfa_pending"] = {"user_id": user.id, "at": time.time()}
                return redirect(url_for("auth.login_verify"))
            login_user(user)
            return redirect(url_for("dashboard.index"))

        flash("Incorrect email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/login/verify", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("5 per minute;20 per hour", key_func=_pending_mfa_user_id, methods=["POST"])
def login_verify():
    pending = session.get("mfa_pending")
    if not pending or time.time() - pending["at"] > MFA_PENDING_SECONDS:
        session.pop("mfa_pending", None)
        if pending:
            flash("That took too long. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, pending["user_id"])
    if not user or not user.mfa_enabled:
        session.pop("mfa_pending", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        method = mfa.verify_login_code(user, request.form.get("code", ""))
        if method:
            db.session.commit()
            session.pop("mfa_pending", None)
            login_user(user)
            if method == "backup":
                flash(
                    f"Backup code used. You have {mfa.remaining_backup_codes(user)} left.",
                    "success",
                )
            return redirect(url_for("dashboard.index"))

        flash("That code didn't work. Try the current code from your app.", "error")

    return render_template("login_verify.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
