
from pydantic import BaseModel, ConfigDict, Field


class IncidentMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_incidents: int = Field(ge=0)
    incidents_by_status: dict[str, int]
    incidents_by_priority: dict[str, int]
    incidents_by_service: dict[str, int]
    resolved_incidents: int = Field(ge=0)
    average_mttr_seconds: float | None = Field(default=None, ge=0)
