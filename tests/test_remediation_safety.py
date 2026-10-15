
import uuid

import pytest

from app.db.models import Incident
from app.services.remediation_record_service import (
    create_remediation_attempt,
)


def create_test_incident(db_session):
    incident = Incident(
        id=str(uuid.uuid4()),
        title="Test service incident",
        description="Test incident for remediation safety",
        service_name="test-service",
        priority="high",
        status="open",
    )
    db_session.add(incident)
    db_session.flush()
    return incident


def test_rejects_nonexistent_incident(db_session):
    plan = {
        "incident_id": str(uuid.uuid4()),
        "rule_id": "service_unavailable",
        "action": "restart_service",
        "description": "Prepare a restart.",
        "risk_level": "high",
        "requires_approval": True,
    }

    with pytest.raises(ValueError, match="Incident does not exist"):
        create_remediation_attempt(db_session, plan)


def test_rejects_high_risk_plan_without_approval(db_session):
    incident = create_test_incident(db_session)

    plan = {
        "incident_id": incident.id,
        "rule_id": "service_unavailable",
        "action": "restart_service",
        "description": "Prepare a restart.",
        "risk_level": "high",
        "requires_approval": False,
    }

    with pytest.raises(ValueError, match="requires approval"):
        create_remediation_attempt(db_session, plan)


def test_rejects_unknown_risk_level(db_session):
    incident = create_test_incident(db_session)

    plan = {
        "incident_id": incident.id,
        "rule_id": "service_unavailable",
        "action": "restart_service",
        "description": "Prepare a restart.",
        "risk_level": "extreme",
        "requires_approval": True,
    }

    with pytest.raises(ValueError, match="Invalid remediation risk level"):
        create_remediation_attempt(db_session, plan)
