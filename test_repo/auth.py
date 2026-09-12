"""
auth.py — Authentication utilities for the test repo.
Used to validate that the chunker correctly splits at function/class boundaries.
"""

import hashlib
import hmac
import os
import time
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

TOKEN_EXPIRY_SECONDS = 3600   # 1 hour
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-please-change")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sign(payload: str, secret: str) -> str:
    """Return an HMAC-SHA256 hex digest of *payload* signed with *secret*."""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def _now() -> int:
    """Return current UTC epoch time as an integer."""
    return int(time.time())


# ──────────────────────────────────────────────────────────────────────────────
# Token generation / validation
# ──────────────────────────────────────────────────────────────────────────────

def generate_token(user_id: str, expiry: int = TOKEN_EXPIRY_SECONDS) -> str:
    """
    Generate a simple signed token for *user_id*.

    Format: <user_id>.<expires_at>.<signature>

    This is intentionally simplified for demo purposes — use JWT in production.
    """
    expires_at = _now() + expiry
    payload = f"{user_id}.{expires_at}"
    sig = _sign(payload, SECRET_KEY)
    return f"{payload}.{sig}"


def validate_token(token: str) -> Optional[str]:
    """
    Validate a token produced by generate_token().

    Returns the user_id on success, or None if the token is invalid/expired.
    """
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts

        # Constant-time comparison to prevent timing attacks
        expected_sig = _sign(payload, SECRET_KEY)
        if not hmac.compare_digest(sig, expected_sig):
            return None

        user_id, expires_at_str = payload.split(".", 1)
        if _now() > int(expires_at_str):
            return None  # token expired

        return user_id

    except (ValueError, AttributeError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Password utilities
# ──────────────────────────────────────────────────────────────────────────────

class PasswordHasher:
    """
    Simple salted-SHA256 password hasher.

    In a real application, use bcrypt or Argon2 via passlib.
    """

    SALT_BYTES = 16

    @staticmethod
    def hash(password: str) -> str:
        """Return a 'salt$digest' string suitable for storage."""
        salt = os.urandom(PasswordHasher.SALT_BYTES).hex()
        digest = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def verify(password: str, stored: str) -> bool:
        """Return True if *password* matches the *stored* hash."""
        try:
            salt, digest = stored.split("$", 1)
            expected = hashlib.sha256((salt + password).encode()).hexdigest()
            return hmac.compare_digest(digest, expected)
        except ValueError:
            return False


# ──────────────────────────────────────────────────────────────────────────────
# Role-based access
# ──────────────────────────────────────────────────────────────────────────────

ROLES: dict[str, list[str]] = {
    "admin":  ["read", "write", "delete", "manage_users"],
    "editor": ["read", "write"],
    "viewer": ["read"],
}


def has_permission(role: str, permission: str) -> bool:
    """Return True if *role* includes *permission*."""
    return permission in ROLES.get(role, [])
