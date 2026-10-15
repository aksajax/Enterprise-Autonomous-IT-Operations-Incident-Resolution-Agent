
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.models import (
    AuditLog,
    Base,
    Incident,
    RemediationAttempt,
    User,
)
from app.db.session import get_db
from app.main import app
from app.services.remediation_executor import ExecutionResult


@pytest.fixture
def remediation_client():
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
            operator = User(
                username="remediation.operator",
                password_hash=hash_password("Strong-Password-123!"),
                role="operator",
                is_active=True,
            )
            viewer = User(
                username="remediation.viewer",
                password_hash=hash_password("Strong-Password-123!"),
                role="viewer",
                is_active=True,
            )
            incident = Incident(
                id=str(uuid.uuid4()),
                title="Test service incident",
                description="Service is unavailable",
                service_name="test-service",
                source="automated-test",
                priority="high",
                status="open",
            )
            db.add_all([operator, viewer, incident])
            db.flush()

            approved_attempt = RemediationAttempt(
                incident_id=incident.id,
                rule_id="service_unavailable",
                action="restart_service",
                description="Simulate restarting the unavailable service",
                risk_level="high",
                requires_approval=True,
                status="approved",
                approved_by=operator.id,
                approved_at=datetime.now(timezone.utc),
            )
            unapproved_attempt = RemediationAttempt(
                incident_id=incident.id,
                rule_id="service_unavailable",
                action="restart_service",
                description="Restart requires approval",
                risk_level="high",
                requires_approval=True,
                status="pending_approval",
            )
            db.add_all([approved_attempt, unapproved_attempt])
            db.commit()

            ids = {
                "incident_id": incident.id,
                "approved_attempt_id": approved_attempt.id,
                "unapproved_attempt_id": unapproved_attempt.id,
                "operator_id": operator.id,
            }

        with TestClient(app) as client:
            yield client, TestSession, ids

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": "Strong-Password-123!",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_approved_remediation_executes_successfully(remediation_client):
    client, _, ids = remediation_client
    token = login(client, "remediation.operator")

    response = client.post(
        f"/api/v1/remediations/{ids['approved_attempt_id']}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    assert "SIMULATED execution completed" in body["execution_result"]
    assert "No infrastructure changes were made" in body["execution_result"]


def test_unapproved_remediation_cannot_execute(remediation_client):
    client, _, ids = remediation_client
    token = login(client, "remediation.operator")

    response = client.post(
        f"/api/v1/remediations/{ids['unapproved_attempt_id']}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


def test_remediation_cannot_execute_twice(remediation_client):
    client, _, ids = remediation_client
    token = login(client, "remediation.operator")
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/api/v1/remediations/{ids['approved_attempt_id']}/execute"

    first_response = client.post(url, headers=headers)
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(url, headers=headers)
    assert second_response.status_code == 409


def test_viewer_cannot_execute_remediation(remediation_client):
    client, _, ids = remediation_client
    token = login(client, "remediation.viewer")

    response = client.post(
        f"/api/v1/remediations/{ids['approved_attempt_id']}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_execution_result_and_audit_events_are_persisted(
    remediation_client,
):
    client, TestSession, ids = remediation_client
    token = login(client, "remediation.operator")
    attempt_id = ids["approved_attempt_id"]

    response = client.post(
        f"/api/v1/remediations/{attempt_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    with TestSession() as db:
        attempt = db.get(RemediationAttempt, attempt_id)
        assert attempt is not None
        assert attempt.status == "succeeded"
        assert "SIMULATED execution completed" in attempt.execution_result

        audit_events = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.resource_id == str(attempt_id)
                )
            ).all()
        )
        actions = {event.action for event in audit_events}

        assert "remediation_execution_started" in actions
        assert "remediation_execution_succeeded" in actions

        for event in audit_events:
            if event.details:
                assert isinstance(json.loads(event.details), dict)



def test_executor_failure_is_persisted(remediation_client, monkeypatch):
    client, TestSession, ids = remediation_client
    attempt_id = ids["approved_attempt_id"]
    token = login(client, "remediation.operator")

    def fake_executor(*, action, description, risk_level):
        return ExecutionResult(
            success=False,
            message="Simulated failure for testing",
        )

    monkeypatch.setattr(
        "app.api.routes.remediation.execute_remediation",
        fake_executor,
    )

    response = client.post(
        f"/api/v1/remediations/{attempt_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["execution_result"] == (
        "Simulated failure for testing"
    )

    with TestSession() as db:
        attempt = db.get(RemediationAttempt, attempt_id)
        assert attempt.status == "failed"
        assert attempt.execution_result == "Simulated failure for testing"

        events = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.resource_id == str(attempt_id)
                )
            ).all()
        )
        assert any(
            event.action == "remediation_execution_failed"
            for event in events
        )

def test_executor_exception_marks_attempt_failed(
    remediation_client,
    monkeypatch,
):
    client, TestSession, ids = remediation_client
    attempt_id = ids["approved_attempt_id"]
    token = login(client, "remediation.operator")

    def failing_executor(*, action, description, risk_level):
        raise RuntimeError("Unexpected executor error")

    monkeypatch.setattr(
        "app.api.routes.remediation.execute_remediation",
        failing_executor,
    )

    response = client.post(
        f"/api/v1/remediations/{attempt_id}/execute",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 500

    with TestSession() as db:
        attempt = db.get(RemediationAttempt, attempt_id)
        assert attempt is not None
        assert attempt.status == "failed"
        assert attempt.execution_result == (
            "Execution failed due to an internal error."
        )

        events = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.resource_id == str(attempt_id)
                )
            ).all()
        )

        assert any(
            event.action == "remediation_execution_failed"
            for event in events
        )
