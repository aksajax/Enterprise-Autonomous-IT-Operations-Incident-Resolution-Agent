
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def auth_client():
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
            db.add_all(
                [
                    User(
                        username="test.operator",
                        password_hash=hash_password(
                            "Strong-Test-Password-123!"
                        ),
                        role="operator",
                        is_active=True,
                    ),
                    User(
                        username="test.viewer",
                        password_hash=hash_password(
                            "Strong-Viewer-Password-123!"
                        ),
                        role="viewer",
                        is_active=True,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            yield client

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_returns_access_token(auth_client: TestClient):
    token = login(
        auth_client,
        "test.operator",
        "Strong-Test-Password-123!",
    )
    assert token


def test_login_rejects_wrong_password(auth_client: TestClient):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "test.operator",
            "password": "Wrong-Password-123!",
        },
    )
    assert response.status_code == 401


def test_me_requires_authentication(auth_client: TestClient):
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_authenticated_user(auth_client: TestClient):
    token = login(
        auth_client,
        "test.operator",
        "Strong-Test-Password-123!",
    )
    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "test.operator"
    assert response.json()["role"] == "operator"
    assert "password_hash" not in response.json()


def test_invalid_token_cannot_access_incidents(
    auth_client: TestClient,
):
    response = auth_client.get(
        "/api/v1/incidents",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


def test_viewer_cannot_create_incidents(auth_client: TestClient):
    token = login(
        auth_client,
        "test.viewer",
        "Strong-Viewer-Password-123!",
    )
    response = auth_client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Unauthorized incident",
            "description": "Viewer should not create incidents.",
            "service_name": "test-service",
            "source": "automated-test",
            "priority": "low",
        },
    )

    assert response.status_code == 403
