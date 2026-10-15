
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RemediationPlanResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: int
    incident_id: str
    rule_id: str | None
    action: str
    description: str
    risk_level: str
    requires_approval: bool
    status: str
    approved_by: int | None
    approved_at: datetime | None
    execution_result: str | None
    created_at: datetime
    updated_at: datetime


class RemediationRejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class RemediationHistoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    items: list[RemediationPlanResponse]
    total: int
