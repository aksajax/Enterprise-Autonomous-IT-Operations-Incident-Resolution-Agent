
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def metrics_client():
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
            viewer = User(
                username="metrics.viewer",
                password_hash=hash_password("Viewer-Password-123!"),
                role="viewer",
                is_active=True,
            )
            operator = User(
                username="metrics.operator",
                password_hash=hash_password("Operator-Password-123!"),
                role="operator",
                is_active=True,
            )

            db.add_all([viewer, operator])
            db.commit()

            viewer_token = create_access_token(viewer.id)
            operator_token = create_access_token(operator.id)

        with TestClient(app) as client:
            yield client, viewer_token, operator_token

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_metrics_requires_authentication(metrics_client):
    client, _, _ = metrics_client

    response = client.get("/api/v1/metrics")

    assert response.status_code == 401


def test_metrics_returns_empty_database_counts(metrics_client):
    client, viewer_token, _ = metrics_client

    response = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_incidents"] == 0
    assert body["incidents_by_service"] == {}
    assert body["resolved_incidents"] == 0
    assert body["average_mttr_seconds"] is None
    assert all(count == 0 for count in body["incidents_by_status"].values())
    assert all(count == 0 for count in body["incidents_by_priority"].values())


def test_metrics_reflect_created_incident(metrics_client):
    client, viewer_token, operator_token = metrics_client

    operator_headers = {
        "Authorization": f"Bearer {operator_token}",
    }
    viewer_headers = {
        "Authorization": f"Bearer {viewer_token}",
    }

    incident_payload = {
        "title": "Metrics integration test",
        "description": "Verify metrics count a persisted incident.",
        "service_name": "payments-api",
        "source": "automated_test",
        "priority": "high",
    }

    create_response = client.post(
        "/api/v1/incidents",
        headers=operator_headers,
        json=incident_payload,
    )

    assert create_response.status_code in (200, 201), create_response.text

    metrics_response = client.get(
        "/api/v1/metrics",
        headers=viewer_headers,
    )

    assert metrics_response.status_code == 200

    body = metrics_response.json()

    assert body["total_incidents"] == 1
    assert body["incidents_by_status"]["open"] == 1
    assert body["incidents_by_priority"]["high"] == 1
    assert body["incidents_by_service"]["payments-api"] == 1
    assert body["resolved_incidents"] == 0
    assert body["average_mttr_seconds"] is None
    