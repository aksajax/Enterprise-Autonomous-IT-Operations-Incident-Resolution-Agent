
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """Return the active user identified by a valid access token."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload["sub"]
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized from None

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_roles(
    *allowed_roles: UserRole,
) -> Callable:
    """Create a dependency that permits only the specified roles."""

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in {
            role.value for role in allowed_roles
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker
