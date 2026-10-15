
from types import SimpleNamespace

import pytest

from app.services.remediation_service import generate_remediation_plan


@pytest.mark.parametrize(
    ("title", "description", "expected_rule", "expected_action"),
    [
        (
            "HTTP 500 errors",
            "The API reports repeated 500 errors",
            "high_error_rate",
            "investigate_service_health",
        ),
        (
            "Service unavailable",
            "Connection refused by the application service",
            "service_unavailable",
            "restart_service",
        ),
        (
            "Disk full",
            "Disk space has reached its limit",
            "disk_capacity",
            "inspect_disk_capacity",
        ),
        (
            "Database connection failure",
            "Database connection timeout",
            "database_connectivity",
            "investigate_database_connectivity",
        ),
    ],
)
def test_known_incident_generates_matching_plan(
    title,
    description,
    expected_rule,
    expected_action,
):
    incident = SimpleNamespace(
        id=101,
        title=title,
        description=description,
        service_name="payments-api",
    )

    plan = generate_remediation_plan(incident)

    assert plan["matched"] is True
    assert plan["rule_id"] == expected_rule
    assert plan["action"] == expected_action
    assert plan["incident_id"] == 101
    assert plan["execution_status"] == "not_executed"


def test_high_risk_action_requires_approval():
    incident = SimpleNamespace(
        id=102,
        title="Service unavailable",
        description="The service is down",
        service_name="payments-api",
    )

    plan = generate_remediation_plan(incident)

    assert plan["action"] == "restart_service"
    assert plan["risk_level"] == "high"
    assert plan["requires_approval"] is True


def test_low_risk_action_does_not_require_approval():
    incident = SimpleNamespace(
        id=103,
        title="HTTP 500 errors",
        description="High error rate detected",
        service_name="payments-api",
    )

    plan = generate_remediation_plan(incident)

    assert plan["risk_level"] == "low"
    assert plan["requires_approval"] is False


def test_unknown_incident_requires_manual_investigation():
    incident = SimpleNamespace(
        id=104,
        title="Unexpected application behavior",
        description="No known error pattern was detected",
        service_name="payments-api",
    )

    plan = generate_remediation_plan(incident)

    assert plan["matched"] is False
    assert plan["action"] is None
    assert plan["requires_approval"] is True
    assert plan["execution_status"] == "not_executed"
