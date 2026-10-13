import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.core.security import create_access_token, hash_password
from app.db.models import Base, User



@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestSession = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestSession() as db:
            user = User(
                username="test.operator",
                password_hash=hash_password(
                    "Strong-Test-Password-123!"
                ),
                role="operator",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            token = create_access_token(user.id)

        with TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        ) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()



def create_payload() -> dict:
    return {
        "title": "Production API returning errors",
        "description": "The production API is returning HTTP 500 errors.",
        "service_name": "payments-api",
        "source": "automated-monitor",
        "priority": "high",
    }


def test_create_incident(client: TestClient) -> None:
    response = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    )

    assert response.status_code == 201

    body = response.json()
    assert body["title"] == "Production API returning errors"
    assert body["status"] == "open"
    assert body["priority"] == "high"
    assert body["id"]
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == "created"


def test_get_incident(client: TestClient) -> None:
    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    ).json()

    response = client.get(
        f"/api/v1/incidents/{created['id']}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_missing_incident_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/incidents/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


def test_list_and_filter_incidents(client: TestClient) -> None:
    client.post("/api/v1/incidents", json=create_payload())

    payload = create_payload()
    payload["priority"] = "critical"
    client.post("/api/v1/incidents", json=payload)

    response = client.get(
        "/api/v1/incidents",
        params={"priority": "critical", "limit": 10, "offset": 0},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["priority"] == "critical"


def test_incident_lifecycle(client: TestClient) -> None:
    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    ).json()

    incident_id = created["id"]

    investigating = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "investigating"},
    )

    assert investigating.status_code == 200
    assert investigating.json()["status"] == "investigating"

    resolved = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={
            "status": "resolved",
            "root_cause": "Database connection pool exhausted",
            "resolution": "An operator adjusted the connection pool.",
        },
    )

    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
    assert len(resolved.json()["events"]) == 3


def test_resolution_requires_evidence(client: TestClient) -> None:
    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    ).json()

    response = client.patch(
        f"/api/v1/incidents/{created['id']}/status",
        json={"status": "resolved"},
    )

    assert response.status_code == 422


def test_invalid_status_transition_returns_409(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    ).json()

    response = client.patch(
        f"/api/v1/incidents/{created['id']}/status",
        json={"status": "resolved"},
    )

    # The transition is invalid because the incident is still open.
    assert response.status_code == 422

    response = client.patch(
        f"/api/v1/incidents/{created['id']}/status",
        json={"status": "closed"},
    )

    assert response.status_code == 200

    response = client.patch(
        f"/api/v1/incidents/{created['id']}/status",
        json={"status": "investigating"},
    )

    assert response.status_code == 409


def test_blank_title_is_rejected(client: TestClient) -> None:
    payload = create_payload()
    payload["title"] = "   "

    response = client.post(
        "/api/v1/incidents",
        json=payload,
    )

    assert response.status_code == 422