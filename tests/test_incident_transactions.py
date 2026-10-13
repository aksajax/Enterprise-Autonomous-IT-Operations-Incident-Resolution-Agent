
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Incident
from app.schemas.incident import IncidentCreate, IncidentPriority
from app.services.incident_service import create_incident


def test_create_incident_leaves_transaction_to_caller() -> None:
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

    try:
        with TestSession() as db:
            payload = IncidentCreate(
                title="Database transaction test",
                description="Verify caller-controlled transactions.",
                service_name="test-service",
                source="automated-test",
                priority=IncidentPriority.HIGH,
            )

            incident = create_incident(db, payload)

            assert incident.id is not None
            assert db.in_transaction()

            count_before_rollback = db.scalar(
                select(func.count()).select_from(Incident)
            )
            assert count_before_rollback == 1

            db.rollback()

        with Session(engine) as verification_db:
            count_after_rollback = verification_db.scalar(
                select(func.count()).select_from(Incident)
            )
            assert count_after_rollback == 0

    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
