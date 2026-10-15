
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.metrics import IncidentMetricsResponse
from app.services.metrics_service import get_incident_metrics


router = APIRouter(prefix="/metrics", tags=["Metrics"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=IncidentMetricsResponse,
    summary="Get incident operational metrics",
)
def get_metrics_endpoint(
    db: DatabaseSession,
    _: AuthenticatedUser,
) -> IncidentMetricsResponse:
    metrics = get_incident_metrics(db)
    return IncidentMetricsResponse(**metrics)
