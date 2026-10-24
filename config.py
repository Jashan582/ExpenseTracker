import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    IS_PRODUCTION = FLASK_ENV == "production"

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///expense_tracker.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PLAID_CLIENT_ID = os.environ.get("PLAID_CLIENT_ID")
    PLAID_SECRET = os.environ.get("PLAID_SECRET")
    PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox")
    PLAID_COUNTRY_CODES = os.environ.get("PLAID_COUNTRY_CODES", "US,CA").split(",")
    PLAID_PRODUCTS = os.environ.get("PLAID_PRODUCTS", "transactions").split(",")
    # Required for OAuth banks (most Canadian banks, Chase, etc.): after the
    # user logs in on the bank's own site, Plaid sends them back here. Must
    # exactly match a URI under Allowed redirect URIs in the Plaid dashboard,
    # e.g. https://tally.everflowdigital.ca/
    PLAID_REDIRECT_URI = os.environ.get("PLAID_REDIRECT_URI")

    TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    # Session cookies carrying a logged-in user's identity shouldn't be
    # readable by JS or sent over plain HTTP once this is a real deployment
    # holding real bank data.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    # Login rate limits are counted here. The in-memory default is per
    # gunicorn worker (so with 2 workers an attacker effectively gets 2x the
    # limit) and resets on restart — point this at Redis in production,
    # e.g. RATELIMIT_STORAGE_URI=redis://localhost:6379.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
