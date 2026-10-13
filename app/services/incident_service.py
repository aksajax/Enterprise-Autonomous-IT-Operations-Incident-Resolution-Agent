
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Incident, IncidentEvent
from app.schemas.incident import (
    IncidentCreate,
    IncidentPriority,
    IncidentStatus,
    IncidentStatusUpdate,
)


class IncidentNotFoundError(Exception):
    """Raised when an incident does not exist."""


class InvalidIncidentTransitionError(Exception):
    """Raised when an incident status transition is not permitted."""


ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {
        IncidentStatus.INVESTIGATING,
        IncidentStatus.CLOSED,
    },
    IncidentStatus.INVESTIGATING: {
        IncidentStatus.OPEN,
        IncidentStatus.RESOLVED,
    },
    IncidentStatus.RESOLVED: {
        IncidentStatus.INVESTIGATING,
        IncidentStatus.CLOSED,
    },
    IncidentStatus.CLOSED: set(),
}


def create_incident(db: Session, payload: IncidentCreate) -> Incident:
    incident = Incident(
        title=payload.title.strip(),
        description=payload.description.strip(),
        service_name=payload.service_name.strip(),
        source=payload.source.strip(),
        priority=payload.priority.value,
        status=IncidentStatus.OPEN.value,
    )

    incident.events.append(
        IncidentEvent(
            event_type="created",
            old_status=None,
            new_status=IncidentStatus.OPEN.value,
            details="Incident created",
            actor="api",
        )
    )

    db.add(incident)
    db.flush()

    return get_incident(db, incident.id)


def get_incident(db: Session, incident_id: str) -> Incident:
    statement = (
        select(Incident)
        .options(selectinload(Incident.events))
        .where(Incident.id == incident_id)
    )

    incident = db.scalar(statement)

    if incident is None:
        raise IncidentNotFoundError(
            f"Incident '{incident_id}' was not found"
        )

    return incident


def list_incidents(
    db: Session,
    *,
    status: IncidentStatus | None,
    priority: IncidentPriority | None,
    limit: int,
    offset: int,
) -> tuple[list[Incident], int]:
    filters = []

    if status is not None:
        filters.append(Incident.status == status.value)

    if priority is not None:
        filters.append(Incident.priority == priority.value)

    total_statement = (
        select(func.count())
        .select_from(Incident)
        .where(*filters)
    )
    total = db.scalar(total_statement) or 0

    items_statement = (
        select(Incident)
        .where(*filters)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .limit(limit)
        .offset(offset)
    )

    items = list(db.scalars(items_statement).all())

    return items, total


def update_incident_status(
    db: Session,
    incident_id: str,
    payload: IncidentStatusUpdate,
) -> Incident:
    incident = get_incident(db, incident_id)

    current_status = IncidentStatus(incident.status)
    target_status = payload.status

    if target_status == current_status:
        raise InvalidIncidentTransitionError(
            f"Incident is already '{current_status.value}'"
        )

    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidIncidentTransitionError(
            f"Transition from '{current_status.value}' "
            f"to '{target_status.value}' is not permitted"
        )

    incident.status = target_status.value

    if payload.root_cause is not None:
        incident.root_cause = payload.root_cause.strip()

    if payload.resolution is not None:
        incident.resolution = payload.resolution.strip()

    if target_status == IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.now(timezone.utc)
    elif target_status == IncidentStatus.INVESTIGATING:
        incident.resolved_at = None

    incident.events.append(
        IncidentEvent(
            event_type="status_changed",
            old_status=current_status.value,
            new_status=target_status.value,
            details="Incident status updated",
            actor="api",
        )
    )

    db.flush()

    return get_incident(db, incident.id)
