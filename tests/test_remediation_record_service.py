
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Incident, RemediationAttempt
from app.services.remediation_record_service import create_remediation_attempt


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with TestSession() as db:
        try:
            yield db
        finally:
            db.rollback()

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_test_incident(db_session):
    incident = Incident(
        title="Service unavailable",
        description="The application service is down",
        service_name="payments-api",
        source="automated_test",
        priority="high",
        status="open",
    )
    db_session.add(incident)
    db_session.flush()
    return incident


def test_create_low_risk_remediation_attempt(db_session):
    incident = create_test_incident(db_session)

    plan = {
        "incident_id": incident.id,
        "rule_id": "high_error_rate",
        "action": "investigate_service_health",
        "description": "Collect service health information.",
        "risk_level": "low",
        "requires_approval": False,
        "execution_status": "not_executed",
    }

    attempt = create_remediation_attempt(db_session, plan)

    assert attempt.id is not None
    assert attempt.incident_id == incident.id
    assert attempt.action == "investigate_service_health"
    assert attempt.status == "planned"
    assert attempt.requires_approval is False
    assert attempt.execution_result is None


def test_high_risk_remediation_requires_approval(db_session):
    incident = create_test_incident(db_session)

    plan = {
        "incident_id": incident.id,
        "rule_id": "service_unavailable",
        "action": "restart_service",
        "description": "Prepare a service restart.",
        "risk_level": "high",
        "requires_approval": True,
        "execution_status": "not_executed",
    }

    attempt = create_remediation_attempt(db_session, plan)

    assert attempt.status == "pending_approval"
    assert attempt.requires_approval is True
    assert attempt.approved_by is None
    assert attempt.approved_at is None
    assert attempt.execution_result is None


def test_remediation_attempt_can_be_reloaded(db_session):
    incident = create_test_incident(db_session)

    plan = {
        "incident_id": incident.id,
        "rule_id": "disk_capacity",
        "action": "inspect_disk_capacity",
        "description": "Inspect disk usage.",
        "risk_level": "low",
        "requires_approval": False,
        "execution_status": "not_executed",
    }

    attempt = create_remediation_attempt(db_session, plan)
    attempt_id = attempt.id

    db_session.commit()

    saved_attempt = db_session.get(RemediationAttempt, attempt_id)

    assert saved_attempt is not None
    assert saved_attempt.incident_id == incident.id
    assert saved_attempt.rule_id == "disk_capacity"
