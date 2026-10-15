
from typing import Any


REMEDIATION_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "high_error_rate",
        "keywords": ("500", "5xx", "high error rate", "internal server error"),
        "action": "investigate_service_health",
        "description": "Collect service health and recent error information.",
        "risk_level": "low",
        "requires_approval": False,
    },
    {
        "rule_id": "service_unavailable",
        "keywords": ("service unavailable", "connection refused", "service down"),
        "action": "restart_service",
        "description": "Prepare a service restart after checking service health.",
        "risk_level": "high",
        "requires_approval": True,
    },
    {
        "rule_id": "disk_capacity",
        "keywords": ("disk full", "disk space", "storage capacity"),
        "action": "inspect_disk_capacity",
        "description": "Inspect disk usage and identify safe cleanup candidates.",
        "risk_level": "low",
        "requires_approval": False,
    },
    {
        "rule_id": "database_connectivity",
        "keywords": (
            "database connection",
            "database unavailable",
            "connection timeout",
        ),
        "action": "investigate_database_connectivity",
        "description": "Inspect database connectivity and connection errors.",
        "risk_level": "low",
        "requires_approval": False,
    },
]


def generate_remediation_plan(incident: Any) -> dict[str, Any]:
    """Generate a remediation recommendation without executing actions."""

    searchable_text = " ".join(
        str(getattr(incident, field, "") or "")
        for field in ("title", "description", "service_name")
    ).lower()

    matched_rule = next(
        (
            rule
            for rule in REMEDIATION_RULES
            if any(keyword in searchable_text for keyword in rule["keywords"])
        ),
        None,
    )

    if matched_rule is None:
        return {
            "incident_id": incident.id,
            "matched": False,
            "rule_id": None,
            "action": None,
            "description": (
                "No remediation rule matched this incident. "
                "Manual investigation is required."
            ),
            "risk_level": "unknown",
            "requires_approval": True,
            "execution_status": "not_executed",
        }

    return {
        "incident_id": incident.id,
        "matched": True,
        "rule_id": matched_rule["rule_id"],
        "action": matched_rule["action"],
        "description": matched_rule["description"],
        "risk_level": matched_rule["risk_level"],
        "requires_approval": matched_rule["requires_approval"],
        "execution_status": "not_executed",
    }
