from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Tenant(db.Model):
    """One row per client business using the platform."""

    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="tenant", lazy=True)
    categories = db.relationship("Category", backref="tenant", lazy=True)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Authenticator-app MFA. The secret is Fernet-encrypted like Plaid tokens
    # (see app/crypto.py) — anyone holding it can generate valid codes.
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    totp_secret_encrypted = db.Column(db.Text)
    # The 30-second time step of the last accepted code, so a code someone
    # shoulder-surfed can't be replayed within its validity window.
    totp_last_used_step = db.Column(db.Integer)

    plaid_items = db.relationship("PlaidItem", backref="user", lazy=True)
    backup_codes = db.relationship(
        "MfaBackupCode", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class MfaBackupCode(db.Model):
    """Single-use recovery codes for when a user loses their authenticator."""

    __tablename__ = "mfa_backup_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # SHA-256 of the normalized code. The codes are random enough that a
    # slow password hash isn't needed, and this lets us look one up directly.
    code_hash = db.Column(db.String(64), nullable=False, index=True)
    used_at = db.Column(db.DateTime)


class PlaidItem(db.Model):
    """One Plaid 'Item' = one bank login the user connected through Link."""

    __tablename__ = "plaid_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.String(255), unique=True, nullable=False)
    # Encrypted with Fernet before storage — see app/crypto.py
    access_token_encrypted = db.Column(db.Text, nullable=False)
    institution_name = db.Column(db.String(255))
    # Cursor for /transactions/sync — lets us pull only what changed
    transactions_cursor = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    accounts = db.relationship("Account", backref="plaid_item", lazy=True)


class Account(db.Model):
    """A specific card/account under a linked bank connection."""

    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    plaid_item_id = db.Column(db.Integer, db.ForeignKey("plaid_items.id"), nullable=False)
    plaid_account_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    official_name = db.Column(db.String(255))
    mask = db.Column(db.String(8))
    type = db.Column(db.String(50))
    subtype = db.Column(db.String(50))

    transactions = db.relationship("Transaction", backref="account", lazy=True)


class Category(db.Model):
    """
    Spending categories. Seeded with defaults per tenant, but users can
    rename, add, or merge categories — this is the 'track it however
    they want' layer on top of Plaid's own categorization.
    """

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    # Optional: user-picked color for chart bars, hex string
    color = db.Column(db.String(7))
    is_default = db.Column(db.Boolean, default=False)

    rules = db.relationship("CategoryRule", backref="category", lazy=True)


class CategoryRule(db.Model):
    """
    Auto-assigns a category based on a merchant name match, so users
    don't have to manually tag every transaction. First match wins.
    """

    __tablename__ = "category_rules"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Simple case-insensitive substring match against merchant_name, e.g. "starbucks"
    match_text = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.Integer, default=0)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    plaid_transaction_id = db.Column(db.String(255), unique=True, nullable=False)
    merchant_name = db.Column(db.String(255))
    name = db.Column(db.String(255))  # Plaid's raw description, fallback if no merchant_name
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # positive = money out, per Plaid convention
    iso_currency_code = db.Column(db.String(10))
    date = db.Column(db.Date, nullable=False, default=date.today)
    pending = db.Column(db.Boolean, default=False)
    # Plaid's own category, kept as a fallback/reference alongside our custom one
    plaid_category_primary = db.Column(db.String(120))
    # Populated only for institutions that report which sub-account/cardholder
    # made the charge (e.g. a business card with multiple named cards on one
    # account). Most institutions don't report this — expect it to be null
    # far more often than not.
    account_owner = db.Column(db.String(255))