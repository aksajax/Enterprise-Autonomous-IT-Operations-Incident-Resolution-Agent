
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import AuditLog, Base, Incident, User
from app.db.session import get_db
from app.main import app


PASSWORD = "Strong-Test-Password-123!"


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
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestSession() as db:
            user = User(
                username="test.operator",
                password_hash=hash_password(PASSWORD),
                role="operator",
                is_active=True,
            )
            db.add(user)
            db.commit()
            user_id = user.id
            token = create_access_token(user.id)

        with TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            yield client, TestSession, user_id

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_payload() -> dict:
    return {
        "title": "Production API returning errors",
        "description": "The production API is returning HTTP 500 errors.",
        "service_name": "payments-api",
        "source": "automated-monitor",
        "priority": "high",
    }


def test_incident_creation_persists_audit_record(audit_client):
    client, TestSession, user_id = audit_client

    response = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    )

    assert response.status_code == 201
    incident_id = response.json()["id"]

    with TestSession() as db:
        event = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "incident_created",
                AuditLog.resource_id == incident_id,
            )
        )

        assert event is not None
        assert event.actor_user_id == user_id
        assert event.actor_username == "test.operator"
        assert event.resource_type == "incident"
        assert event.request_id == response.headers["X-Request-ID"]

        details = json.loads(event.details)
        assert details["priority"] == "high"
        assert details["status"] == "open"


def test_status_change_persists_audit_record(audit_client):
    client, TestSession, user_id = audit_client

    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    )
    assert created.status_code == 201

    incident_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "investigating"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "investigating"

    with TestSession() as db:
        event = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "incident_status_changed",
                AuditLog.resource_id == incident_id,
            )
        )

        assert event is not None
        assert event.actor_user_id == user_id
        assert event.actor_username == "test.operator"
        assert event.request_id == response.headers["X-Request-ID"]

        details = json.loads(event.details)
        assert details == {
            "new_status": "investigating",
            "old_status": "open",
        }


def test_incident_creation_rolls_back_when_audit_fails(
    audit_client,
    monkeypatch,
):
    import app.api.routes.incidents as incident_routes

    client, TestSession, _ = audit_client

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(
        incident_routes,
        "record_audit_event",
        fail_audit,
    )

    response = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    )

    assert response.status_code == 500

    with TestSession() as db:
        incident_count = db.scalar(
            select(func.count()).select_from(Incident)
        )
        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "incident_created")
        )

        assert incident_count == 0
        assert audit_count == 0


def test_status_change_rolls_back_when_audit_fails(
    audit_client,
    monkeypatch,
):
    import app.api.routes.incidents as incident_routes

    client, TestSession, _ = audit_client

    created = client.post(
        "/api/v1/incidents",
        json=create_payload(),
    )
    assert created.status_code == 201

    incident_id = created.json()["id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(
        incident_routes,
        "record_audit_event",
        fail_audit,
    )

    response = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "investigating"},
    )

    assert response.status_code == 500

    with TestSession() as db:
        incident = db.scalar(
            select(Incident).where(Incident.id == incident_id)
        )
        assert incident is not None
        assert incident.status == "open"

        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "incident_status_changed",
                AuditLog.resource_id == incident_id,
            )
        )
        assert audit_count == 0
