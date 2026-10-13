
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.models import AuditLog, Base, User
from app.db.session import get_db
from app.main import app


VALID_PASSWORD = "Strong-Test-Password-123!"


@pytest.fixture
def audit_client():
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

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestSession() as db:
            db.add(
                User(
                    username="test.operator",
                    password_hash=hash_password(VALID_PASSWORD),
                    role="operator",
                    is_active=True,
                )
            )
            db.commit()

        with TestClient(app) as client:
            yield client, TestSession

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_successful_login_is_audited(audit_client):
    client, TestSession = audit_client

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "test.operator",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]

    with TestSession() as db:
        event = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "login_success")
        )

        assert event is not None
        assert event.actor_username == "test.operator"
        assert event.resource_type == "user"
        assert event.request_id is not None
        assert event.created_at is not None


def test_failed_login_is_audited(audit_client):
    client, TestSession = audit_client

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "test.operator",
            "password": "Wrong-Password-123!",
        },
    )

    assert response.status_code == 401

    with TestSession() as db:
        event = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "login_failed")
        )

        assert event is not None
        assert event.actor_username == "test.operator"
        assert event.resource_type == "user"
        assert event.request_id is not None


def test_unknown_user_login_is_audited(audit_client):
    client, TestSession = audit_client

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "unknown.user",
            "password": "Wrong-Password-123!",
        },
    )

    assert response.status_code == 401

    with TestSession() as db:
        event = db.scalar(
            select(AuditLog)
            .where(AuditLog.action == "login_failed")
        )

        assert event is not None
        assert event.actor_username == "unknown.user"
        assert event.actor_user_id is None
