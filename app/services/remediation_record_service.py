
from sqlalchemy.orm import Session

from app.db.models import Incident, RemediationAttempt


VALID_RISK_LEVELS = {"low", "medium", "high", "unknown"}


def create_remediation_attempt(
    db: Session,
    plan: dict,
) -> RemediationAttempt:
    """Validate and persist a remediation plan without executing it."""

    incident_id = plan.get("incident_id")
    action = plan.get("action")
    risk_level = plan.get("risk_level")
    description = plan.get("description")
    requires_approval = plan.get("requires_approval")

    # Incident IDs in this project are UUID strings.
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise ValueError("A valid incident_id is required")

    if db.get(Incident, incident_id) is None:
        raise ValueError("Incident does not exist")

    if not isinstance(action, str) or not action.strip():
        raise ValueError("A valid remediation action is required")

    if risk_level not in VALID_RISK_LEVELS:
        raise ValueError("Invalid remediation risk level")

    if not isinstance(description, str) or not description.strip():
        raise ValueError("A remediation description is required")

    if not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be a boolean")

    # Fail closed for medium-, high-, and unknown-risk actions.
    if risk_level != "low" and not requires_approval:
        raise ValueError("Non-low-risk remediation requires approval")

    attempt = RemediationAttempt(
        incident_id=incident_id,
        rule_id=plan.get("rule_id"),
        action=action.strip(),
        description=description.strip(),
        risk_level=risk_level,
        requires_approval=requires_approval,
        status=(
            "pending_approval"
            if requires_approval
            else "planned"
        ),
    )

    db.add(attempt)
    db.flush()

    return attempt
