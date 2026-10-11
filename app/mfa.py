"""
Authenticator-app (TOTP) MFA plus single-use backup codes.

Routes call verify_login_code() for the sign-in step, and the setup flow
uses match_totp() against a secret that isn't saved on the user yet.
"""
import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime

import pyotp
import qrcode
import qrcode.image.svg

from app import db
from app.crypto import decrypt_token, encrypt_token
from app.models import MfaBackupCode

ISSUER = "Tally"
BACKUP_CODE_COUNT = 10
# Accept the previous and next 30-second code too, to allow for phone clock drift.
DRIFT_STEPS = 1


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// link — shown as a QR code, and as a tap-to-open link on
    phones where the authenticator app is on the same device."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg(uri: str) -> str:
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def _normalize(code: str) -> str:
    return "".join(code.split()).replace("-", "").lower()


def match_totp(secret: str, code: str, last_used_step: int | None = None) -> int | None:
    """Return the time step the code matches, or None. Steps at or before
    last_used_step are rejected so a code can't be used twice."""
    code = _normalize(code)
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(time.time()) // totp.interval
    for step in range(now_step - DRIFT_STEPS, now_step + DRIFT_STEPS + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp.at(step * totp.interval), code):
            return step
    return None


def enable(user, secret: str, step: int) -> list[str]:
    user.totp_secret_encrypted = encrypt_token(secret)
    user.totp_last_used_step = step
    user.mfa_enabled = True
    return regenerate_backup_codes(user)


def disable(user):
    user.mfa_enabled = False
    user.totp_secret_encrypted = None
    user.totp_last_used_step = None
    user.backup_codes.clear()


def _hash_backup_code(code: str) -> str:
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def regenerate_backup_codes(user) -> list[str]:
    """Replace the user's backup codes. Returns the plaintext codes — this is
    the only time they exist, so show them to the user right away."""
    user.backup_codes.clear()
    codes = []
    for _ in range(BACKUP_CODE_COUNT):
        raw = secrets.token_hex(5)  # 10 hex chars, 40 bits
        codes.append(f"{raw[:5]}-{raw[5:]}")
        user.backup_codes.append(MfaBackupCode(code_hash=_hash_backup_code(raw)))
    return codes


def remaining_backup_codes(user) -> int:
    return sum(1 for c in user.backup_codes if c.used_at is None)


def verify_totp(user, code: str) -> bool:
    step = match_totp(decrypt_token(user.totp_secret_encrypted), code, user.totp_last_used_step)
    if step is None:
        return False
    user.totp_last_used_step = step
    return True


def use_backup_code(user, code: str) -> bool:
    code_hash = _hash_backup_code(code)
    backup = MfaBackupCode.query.filter_by(
        user_id=user.id, code_hash=code_hash, used_at=None
    ).first()
    if not backup:
        return False
    backup.used_at = datetime.utcnow()
    return True


def verify_login_code(user, code: str) -> str | None:
    """Check a sign-in code. Returns "totp" or "backup" for whichever kind
    matched, or None. Caller commits the session."""
    if verify_totp(user, code):
        return "totp"
    if use_backup_code(user, code):
        return "backup"
    return None
