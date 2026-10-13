
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import AuditLog, Base, User
from app.core.security import hash_password
from app.services.audit_service import record_audit_event


def test_record_audit_event():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            user = User(
                username="audit.operator",
                password_hash=hash_password("Strong-Audit-Password-123!"),
                role="operator",
                is_active=True,
            )
            db.add(user)
            db.flush()

            event = record_audit_event(
                db,
                action="incident_created",
                resource_type="incident",
                actor_user_id=user.id,
                actor_username=user.username,
                resource_id="incident-123",
                details={"priority": "high", "source": "manual"},
                ip_address="127.0.0.1",
                request_id="request-123",
            )

            assert event.id is not None
            db.commit()

            saved = db.scalar(
                select(AuditLog).where(AuditLog.id == event.id)
            )
            assert saved is not None
            assert saved.action == "incident_created"
            assert saved.actor_username == "audit.operator"
            assert saved.resource_id == "incident-123"
            assert json.loads(saved.details) == {
                "priority": "high",
                "source": "manual",
            }
            assert saved.ip_address == "127.0.0.1"
            assert saved.request_id == "request-123"
            assert saved.created_at is not None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
