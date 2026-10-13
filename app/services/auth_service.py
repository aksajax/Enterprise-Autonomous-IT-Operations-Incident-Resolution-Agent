
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.models import User


class InvalidCredentialsError(Exception):
    """Raised when credentials are invalid or the user is inactive."""


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    statement = select(User).where(
        User.username == username.strip()
    )
    return db.scalar(statement)


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User:
    """Authenticate an active user using their stored password hash."""
    user = get_user_by_username(db, username)

    if user is None:
        raise InvalidCredentialsError("Invalid username or password.")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password.")

    if not user.is_active:
        raise InvalidCredentialsError("Invalid username or password.")

    return user


def issue_access_token(user: User) -> str:
    """Issue a token after successful authentication."""
    if not user.is_active:
        raise InvalidCredentialsError("User is inactive.")

    return create_access_token(user.id)
