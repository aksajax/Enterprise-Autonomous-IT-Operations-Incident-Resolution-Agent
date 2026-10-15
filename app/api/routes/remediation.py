
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import (
    Incident,
    RemediationAttempt,
    User,
)
from app.db.session import get_db
from app.schemas.remediation import (
    RemediationHistoryResponse,
    RemediationPlanResponse,
    RemediationRejectionRequest,
)
from app.services.audit_service import record_audit_event
from app.services.remediation_record_service import (
    create_remediation_attempt,
)
from app.services.remediation_service import (
    generate_remediation_plan,
)

router = APIRouter(prefix="/remediations", tags=["Remediations"])


def _require_remediation_operator(user: User) -> None:
    if user.role not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or operator role required",
        )


def _get_pending_attempt(
    db: Session,
    attempt_id: int,
) -> RemediationAttempt:
    attempt = db.get(RemediationAttempt, attempt_id)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation attempt not found",
        )

    if attempt.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending remediation attempts can be decided",
        )

    if not attempt.requires_approval:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This remediation attempt does not require approval",
        )

    return attempt


@router.post(
    "/incidents/{incident_id}/plan",
    response_model=RemediationPlanResponse,
    summary="Create a remediation plan",
)
def create_remediation_plan_endpoint(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RemediationPlanResponse:
    try:
        incident = db.get(Incident, incident_id)

        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        plan = generate_remediation_plan(incident)
        attempt = create_remediation_attempt(db, plan)

        record_audit_event(
            db=db,
            user_id=current_user.id,
            action="remediation_plan_created",
            resource_type="remediation_attempt",
            resource_id=str(attempt.id),
            details={
                "incident_id": incident_id,
                "action": attempt.action,
                "risk_level": attempt.risk_level,
                "requires_approval": attempt.requires_approval,
            },
        )

        db.commit()
        db.refresh(attempt)

        return RemediationPlanResponse.model_validate(attempt)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{attempt_id}/approve",
    response_model=RemediationPlanResponse,
    summary="Approve a remediation plan",
)
def approve_remediation_endpoint(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RemediationPlanResponse:
    _require_remediation_operator(current_user)

    try:
        attempt = _get_pending_attempt(db, attempt_id)

        attempt.status = "approved"
        attempt.approved_by = current_user.id
        attempt.approved_at = datetime.now(timezone.utc)

        record_audit_event(
            db=db,
            user_id=current_user.id,
            action="remediation_approved",
            resource_type="remediation_attempt",
            resource_id=str(attempt.id),
            details={
                "incident_id": attempt.incident_id,
                "action": attempt.action,
            },
        )

        db.commit()
        db.refresh(attempt)

        return RemediationPlanResponse.model_validate(attempt)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{attempt_id}/reject",
    response_model=RemediationPlanResponse,
    summary="Reject a remediation plan",
)
def reject_remediation_endpoint(
    attempt_id: int,
    payload: RemediationRejectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RemediationPlanResponse:
    _require_remediation_operator(current_user)

    try:
        attempt = _get_pending_attempt(db, attempt_id)

        attempt.status = "rejected"
        attempt.execution_result = f"Rejected: {payload.reason}"

        record_audit_event(
            db=db,
            user_id=current_user.id,
            action="remediation_rejected",
            resource_type="remediation_attempt",
            resource_id=str(attempt.id),
            details={
                "incident_id": attempt.incident_id,
                "action": attempt.action,
                "reason": payload.reason,
            },
        )

        db.commit()
        db.refresh(attempt)

        return RemediationPlanResponse.model_validate(attempt)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get(
    "/incidents/{incident_id}/history",
    response_model=RemediationHistoryResponse,
    summary="Get remediation history for an incident",
)
def get_remediation_history_endpoint(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RemediationHistoryResponse:
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    statement = (
        select(RemediationAttempt)
        .where(RemediationAttempt.incident_id == incident_id)
        .order_by(
            RemediationAttempt.created_at.desc(),
            RemediationAttempt.id.desc(),
        )
    )

    attempts = list(db.scalars(statement).all())

    return RemediationHistoryResponse(
        items=[
            RemediationPlanResponse.model_validate(attempt)
            for attempt in attempts
        ],
        total=len(attempts),
    )
