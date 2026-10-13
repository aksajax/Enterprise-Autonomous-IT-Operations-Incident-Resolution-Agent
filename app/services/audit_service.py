
import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    """Add an audit event to the current database transaction."""

    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=(
            json.dumps(details, sort_keys=True, separators=(",", ":"))
            if details is not None
            else None
        ),
        ip_address=ip_address,
        request_id=request_id,
    )

    db.add(audit_log)
    db.flush()

    return audit_log
