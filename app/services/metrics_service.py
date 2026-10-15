
from datetime import timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Incident
from app.schemas.incident import IncidentPriority, IncidentStatus


def _as_utc(value):
    """Normalize a datetime to UTC for safe duration calculations."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_incident_metrics(db: Session) -> dict[str, Any]:
    """Calculate operational metrics from persisted incident records."""

    total_incidents = db.scalar(
        select(func.count()).select_from(Incident)
    ) or 0

    status_counts = {
        status.value: 0 for status in IncidentStatus
    }
    status_rows = db.execute(
        select(Incident.status, func.count())
        .group_by(Incident.status)
    ).all()

    for incident_status, count in status_rows:
        status_counts[incident_status] = count

    priority_counts = {
        priority.value: 0 for priority in IncidentPriority
    }
    priority_rows = db.execute(
        select(Incident.priority, func.count())
        .group_by(Incident.priority)
    ).all()

    for priority, count in priority_rows:
        priority_counts[priority] = count

    service_rows = db.execute(
        select(Incident.service_name, func.count())
        .group_by(Incident.service_name)
        .order_by(func.count().desc(), Incident.service_name.asc())
    ).all()

    incidents_by_service = {
        service_name: count
        for service_name, count in service_rows
    }

    resolved_rows = db.execute(
        select(Incident.created_at, Incident.resolved_at)
        .where(Incident.resolved_at.is_not(None))
    ).all()

    durations_seconds = []

    for created_at, resolved_at in resolved_rows:
        if created_at is None or resolved_at is None:
            continue

        duration = (
            _as_utc(resolved_at) - _as_utc(created_at)
        ).total_seconds()

        # Exclude invalid negative durations from the MTTR calculation.
        if duration >= 0:
            durations_seconds.append(duration)

    average_mttr_seconds = (
        sum(durations_seconds) / len(durations_seconds)
        if durations_seconds
        else None
    )

    return {
        "total_incidents": total_incidents,
        "incidents_by_status": status_counts,
        "incidents_by_priority": priority_counts,
        "incidents_by_service": incidents_by_service,
        "resolved_incidents": len(resolved_rows),
        "average_mttr_seconds": average_mttr_seconds,
    }
