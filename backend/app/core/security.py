"""Core security utilities for Phase 17A authentication.

Provides:
- Argon2 password hashing / verification via passlib
- JWT access and refresh token creation / decoding
- Password strength validation
"""

from __future__ import annotations

import logging
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

__all__ = [
    "AuthError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "validate_password_strength",
]


class AuthError(Exception):
    """Structured authentication/authorization error."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2.

    Args:
        password: Plaintext password.

    Returns:
        Hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Args:
        plain_password: Plaintext password provided by the user.
        hashed_password: Stored Argon2 hash.

    Returns:
        True when the password matches, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as exc:
        logger.warning("Password verification failed: %s", exc)
        return False


def create_access_token(user_id: str, role: str) -> tuple[str, datetime]:
    """Create a short-lived JWT access token.

    Args:
        user_id: UUID of the authenticated user.
        role: User role string.

    Returns:
        Tuple of (encoded token, expiration datetime).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=getattr(settings, "JWT_ACCESS_TTL_MIN", 30)
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": secrets.token_urlsafe(16),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token, expire


def create_refresh_token(user_id: str, token_version: int) -> tuple[str, datetime]:
    """Create a long-lived JWT refresh token.

    Args:
        user_id: UUID of the authenticated user.
        token_version: Current token_version for the user (for revocation).

    Returns:
        Tuple of (encoded token, expiration datetime).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=getattr(settings, "JWT_REFRESH_TTL_DAYS", 7)
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "token_version": token_version,
        "jti": secrets.token_urlsafe(16),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token, expire


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded token payload dict.

    Raises:
        AuthError: When the token is expired, invalid, or tampered with.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return dict(payload)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired", status_code=401) from exc
    except jwt.JWTClaimsError as exc:
        raise AuthError("Invalid token claims", status_code=401) from exc
    except JWTError as exc:
        raise AuthError("Invalid or tampered token", status_code=401) from exc


class PasswordStrengthError(Exception):
    """Raised when a password does not meet the strength requirements."""


def validate_password_strength(password: str) -> None:
    """Validate that a password meets the minimum strength requirements.

    Requirements:
    - At least 10 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character

    Args:
        password: Plaintext password to validate.

    Raises:
        PasswordStrengthError: When the password does not meet requirements.
    """
    if len(password) < 10:
        raise PasswordStrengthError("Password must be at least 10 characters long")

    if not re.search(r"[A-Z]", password):
        raise PasswordStrengthError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise PasswordStrengthError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", password):
        raise PasswordStrengthError("Password must contain at least one digit")

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\'":\\|,.<>\/?`~ ]', password):
        raise PasswordStrengthError("Password must contain at least one special character")
