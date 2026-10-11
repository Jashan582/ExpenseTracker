"""
Plaid access tokens are effectively the keys to a user's bank connection.
Never store them in plaintext. This wraps Fernet symmetric encryption so
the rest of the app just calls encrypt_token()/decrypt_token().
"""
from cryptography.fernet import Fernet
from flask import current_app


def _fernet():
    key = current_app.config["TOKEN_ENCRYPTION_KEY"]
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with:\n"
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(raw_token: str) -> str:
    return _fernet().encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet().decrypt(encrypted_token.encode()).decode()
