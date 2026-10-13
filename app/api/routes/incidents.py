
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import UserRole
from app.schemas.incident import (
    IncidentCreate,
    IncidentDetail,
    IncidentList,
    IncidentPriority,
    IncidentStatus,
    IncidentStatusUpdate,
)
from app.services.audit_service import record_audit_event
from app.services.incident_service import (
    IncidentNotFoundError,
    InvalidIncidentTransitionError,
    create_incident,
    get_incident,
    list_incidents,
    update_incident_status,
)


router = APIRouter(prefix="/incidents", tags=["Incidents"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
IncidentOperator = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
]


@router.post(
    "",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an incident",
)
def create_incident_endpoint(
    payload: IncidentCreate,
    request: Request,
    db: DatabaseSession,
    current_user: IncidentOperator,
) -> IncidentDetail:
    try:
        incident = create_incident(db, payload)

        record_audit_event(
            db,
            action="incident_created",
            resource_type="incident",
            resource_id=incident.id,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            details={
                "title": incident.title,
                "priority": incident.priority,
                "status": incident.status,
            },
            ip_address=request.client.host if request.client else None,
            request_id=getattr(request.state, "request_id", None),
        )

        db.commit()
        incident = get_incident(db, incident.id)

    except Exception:
        db.rollback()
        raise

    return IncidentDetail.model_validate(incident)


@router.get(
    "",
    response_model=IncidentList,
    summary="List incidents",
)
def list_incidents_endpoint(
    db: DatabaseSession,
    _: AuthenticatedUser,
    incident_status: Annotated[
        IncidentStatus | None,
        Query(alias="status"),
    ] = None,
    priority: IncidentPriority | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> IncidentList:
    items, total = list_incidents(
        db,
        status=incident_status,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    return IncidentList(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetail,
    summary="Get incident details and history",
)
def get_incident_endpoint(
    incident_id: str,
    db: DatabaseSession,
    _: AuthenticatedUser,
) -> IncidentDetail:
    try:
        incident = get_incident(db, incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc

    return IncidentDetail.model_validate(incident)


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentDetail,
    summary="Change incident status",
)
def update_incident_status_endpoint(
    incident_id: str,
    payload: IncidentStatusUpdate,
    request: Request,
    db: DatabaseSession,
    current_user: IncidentOperator,
) -> IncidentDetail:
    try:
        incident = get_incident(db, incident_id)
        old_status = incident.status

        incident = update_incident_status(
            db,
            incident_id,
            payload,
        )

        record_audit_event(
            db,
            action="incident_status_changed",
            resource_type="incident",
            resource_id=incident.id,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            details={
                "old_status": old_status,
                "new_status": incident.status,
            },
            ip_address=request.client.host if request.client else None,
            request_id=getattr(request.state, "request_id", None),
        )

        db.commit()
        incident = get_incident(db, incident.id)

    except IncidentNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc
    except InvalidIncidentTransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return IncidentDetail.model_validate(incident)
