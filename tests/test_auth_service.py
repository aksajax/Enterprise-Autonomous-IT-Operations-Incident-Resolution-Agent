
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models import Base, User
from app.services.auth_service import (
    InvalidCredentialsError,
    authenticate_user,
    issue_access_token,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    try:
        with TestSession() as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def active_user(db):
    user = User(
        username="test.operator",
        password_hash=hash_password("Strong-Test-Password-123!"),
        role="operator",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_password_is_hashed_and_verified():
    password = "Strong-Test-Password-123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Wrong-Password-123!", hashed)


def test_password_requires_minimum_length():
    with pytest.raises(ValueError):
        hash_password("short")


def test_authenticate_active_user(db, active_user):
    user = authenticate_user(
        db,
        "test.operator",
        "Strong-Test-Password-123!",
    )

    assert user.id == active_user.id
    assert user.role == "operator"


def test_invalid_password_is_rejected(db, active_user):
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(
            db,
            "test.operator",
            "Wrong-Password-123!",
        )


def test_unknown_user_is_rejected(db):
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(
            db,
            "missing.user",
            "Strong-Test-Password-123!",
        )


def test_inactive_user_is_rejected(db):
    user = User(
        username="inactive.user",
        password_hash=hash_password("Strong-Test-Password-123!"),
        role="viewer",
        is_active=False,
    )
    db.add(user)
    db.commit()

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(
            db,
            "inactive.user",
            "Strong-Test-Password-123!",
        )


def test_access_token_contains_user_id(active_user):
    token = issue_access_token(active_user)
    payload = decode_access_token(token)

    assert payload["sub"] == active_user.id
    assert payload["type"] == "access"
    assert "exp" in payload


def test_invalid_token_is_rejected():
    import jwt

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("this-is-not-a-valid-token")


def test_invalid_user_id_cannot_create_token():
    with pytest.raises(ValueError):
        create_access_token("not-a-uuid")
