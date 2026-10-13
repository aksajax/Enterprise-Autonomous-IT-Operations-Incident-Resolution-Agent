
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a secure password hash."""
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password without storing or exposing the original."""
    try:
        return password_hash.verify(password, hashed_password)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    """Create a signed JWT access token for a user."""
    try:
        UUID(user_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("user_id must be a valid UUID.") from exc

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Validate a JWT and return its claims."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "iat", "exp", "type"]},
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type.")

    try:
        UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Invalid subject.") from exc

    return payload
