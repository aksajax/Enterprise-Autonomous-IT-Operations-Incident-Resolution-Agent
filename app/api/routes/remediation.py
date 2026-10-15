
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db.models import RemediationAttempt
from app.schemas.remediation import (
    RemediationPlanResponse,
    RemediationRejectionRequest,
)


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
    "/{attempt_id}/approve",
    response_model=RemediationPlanResponse,
    summary="Approve a remediation plan",
)
def approve_remediation_endpoint(
    attempt_id: int,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
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
    db: DatabaseSession,
    current_user: AuthenticatedUser,
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
