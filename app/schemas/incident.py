from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=10000)
    service_name: str = Field(min_length=1, max_length=120)
    source: str = Field(default="manual", min_length=1, max_length=50)
    priority: IncidentPriority = IncidentPriority.MEDIUM

    @model_validator(mode="after")
    def validate_text(self):
        for field_name in ("title", "description", "service_name", "source"):
            value = getattr(self, field_name)

            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")

        return self


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    root_cause: str | None = Field(default=None, max_length=10000)
    resolution: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_resolution(self):
        if self.status == IncidentStatus.RESOLVED:
            if not self.root_cause or not self.root_cause.strip():
                raise ValueError(
                    "root_cause is required when resolving an incident"
                )

            if not self.resolution or not self.resolution.strip():
                raise ValueError(
                    "resolution is required when resolving an incident"
                )

        return self


class IncidentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    old_status: str | None
    new_status: str | None
    details: str | None
    actor: str
    created_at: datetime


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    service_name: str
    source: str
    priority: IncidentPriority
    status: IncidentStatus
    root_cause: str | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class IncidentDetail(IncidentRead):
    events: list[IncidentEventRead]


class IncidentList(BaseModel):
    items: list[IncidentRead]
    total: int
    limit: int
    offset: int