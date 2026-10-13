from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Boolean,
    UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint(
            "role IN ('admin', 'operator', 'viewer')",
            name="ck_users_role",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="viewer",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Incident(Base):
    __tablename__ = "incidents"

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'closed')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_priority",
        ),
        Index("ix_incidents_status_created", "status", "created_at"),
        Index("ix_incidents_priority_created", "priority", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="open",
    )
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.id",
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="api",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    incident: Mapped[Incident] = relationship(back_populates="events")


class AuditLog(Base):
    """Record security and operational actions for accountability."""

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
