
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Incident
from app.services.metrics_service import get_incident_metrics


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_incident(
    db,
    *,
    title,
    service_name,
    priority,
    status,
    created_at,
    resolved_at=None,
):
    incident = Incident(
        title=title,
        description=f"Test incident: {title}",
        service_name=service_name,
        source="automated-test",
        priority=priority,
        status=status,
        created_at=created_at,
        resolved_at=resolved_at,
    )
    db.add(incident)
    db.flush()
    return incident


def test_metrics_calculate_counts_and_mttr(db):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    add_incident(
        db,
        title="Resolved payment incident",
        service_name="payments-api",
        priority="high",
        status="resolved",
        created_at=now - timedelta(minutes=30),
        resolved_at=now,
    )

    add_incident(
        db,
        title="Resolved notification incident",
        service_name="notifications-api",
        priority="critical",
        status="resolved",
        created_at=now - timedelta(minutes=60),
        resolved_at=now,
    )

    add_incident(
        db,
        title="Open payment incident",
        service_name="payments-api",
        priority="high",
        status="open",
        created_at=now,
    )

    db.commit()

    metrics = get_incident_metrics(db)

    assert metrics["total_incidents"] == 3
    assert metrics["incidents_by_status"]["resolved"] == 2
    assert metrics["incidents_by_status"]["open"] == 1
    assert metrics["incidents_by_status"]["investigating"] == 0

    assert metrics["incidents_by_priority"]["high"] == 2
    assert metrics["incidents_by_priority"]["critical"] == 1
    assert metrics["incidents_by_priority"]["low"] == 0

    assert metrics["incidents_by_service"] == {
        "payments-api": 2,
        "notifications-api": 1,
    }

    assert metrics["resolved_incidents"] == 2
    assert metrics["average_mttr_seconds"] == 45 * 60


def test_metrics_handle_empty_database(db):
    metrics = get_incident_metrics(db)

    assert metrics["total_incidents"] == 0
    assert metrics["incidents_by_service"] == {}
    assert metrics["resolved_incidents"] == 0
    assert metrics["average_mttr_seconds"] is None

    assert all(
        count == 0
        for count in metrics["incidents_by_status"].values()
    )
    assert all(
        count == 0
        for count in metrics["incidents_by_priority"].values()
    )


def test_mttr_is_none_when_no_incidents_are_resolved(db):
    now = datetime.now(timezone.utc)

    add_incident(
        db,
        title="Unresolved incident",
        service_name="payments-api",
        priority="medium",
        status="investigating",
        created_at=now,
    )

    db.commit()

    metrics = get_incident_metrics(db)

    assert metrics["total_incidents"] == 1
    assert metrics["resolved_incidents"] == 0
    assert metrics["average_mttr_seconds"] is None
