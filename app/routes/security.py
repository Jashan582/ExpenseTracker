from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user

from app import db, limiter, mfa

security_bp = Blueprint("security", __name__, url_prefix="/settings/security")

# Wrong codes on these pages count against the same budget as sign-in, so
# someone at an unlocked laptop can't brute-force a code to turn MFA off.
code_limit = limiter.limit(
    "5 per minute;20 per hour", key_func=lambda: str(current_user.get_id()),methods=["POST"]
)


@security_bp.route("/")
@login_required
def index():
    return render_template(
        "security.html",
        remaining_codes=mfa.remaining_backup_codes(current_user) if current_user.mfa_enabled else 0,
    )


@security_bp.route("/mfa/setup", methods=["GET", "POST"])
@login_required
@code_limit
def mfa_setup():
    if current_user.mfa_enabled:
        return redirect(url_for("security.index"))

    # Keep the same secret across reloads so the QR code the user already
    # scanned stays valid. It lives only in the session until confirmed.
    secret = session.get("mfa_setup_secret")
    if not secret:
        secret = session["mfa_setup_secret"] = mfa.new_secret()

    if request.method == "POST":
        step = mfa.match_totp(secret, request.form.get("code", ""))
        if step is None:
            flash("That code didn't match. Check your phone's clock and try the current code.", "error")
        else:
            codes = mfa.enable(current_user, secret, step)
            db.session.commit()
            session.pop("mfa_setup_secret", None)
            flash("Two-factor authentication is on.", "success")
            return render_template("mfa_backup_codes.html", codes=codes)

    uri = mfa.provisioning_uri(secret, current_user.email)
    return render_template(
        "mfa_setup.html",
        otpauth_uri=uri,
        qr_svg=mfa.qr_svg(uri),
        secret=secret,
    )


@security_bp.route("/mfa/backup-codes", methods=["POST"])
@login_required
@code_limit
def regenerate_backup_codes():
    if not current_user.mfa_enabled:
        return redirect(url_for("security.index"))
    if not mfa.verify_totp(current_user, request.form.get("code", "")):
        flash("That code didn't work.", "error")
        return redirect(url_for("security.index"))

    codes = mfa.regenerate_backup_codes(current_user)
    db.session.commit()
    flash("New backup codes generated. Your old ones no longer work.", "success")
    return render_template("mfa_backup_codes.html", codes=codes)


@security_bp.route("/mfa/disable", methods=["POST"])
@login_required
@code_limit
def mfa_disable():
    if not current_user.mfa_enabled:
        return redirect(url_for("security.index"))
    if not current_user.check_password(request.form.get("password", "")):
        flash("Incorrect password.", "error")
        return redirect(url_for("security.index"))
    if not mfa.verify_login_code(current_user, request.form.get("code", "")):
        flash("That code didn't work.", "error")
        return redirect(url_for("security.index"))

    mfa.disable(current_user)
    db.session.commit()
    flash("Two-factor authentication is off.", "success")
    return redirect(url_for("security.index"))
