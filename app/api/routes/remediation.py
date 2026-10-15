from datetime import datetime, timezone
from app.services.remediation_executor import ExecutionResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import Incident, RemediationAttempt, User
from app.db.session import get_db
from app.schemas.remediation import (
    RemediationHistoryResponse,
    RemediationPlanResponse,
    RemediationRejectionRequest,
)
from app.services.audit_service import record_audit_event
from app.services.remediation_executor import execute_remediation
from app.services.remediation_record_service import create_remediation_attempt
from app.services.remediation_service import generate_remediation_plan

router = APIRouter(prefix="/remediations", tags=["Remediations"])


def _require_remediation_operator(user: User) -> None:
    if user.role not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or operator role required",
        )


def _get_pending_attempt(db: Session, attempt_id: int) -> RemediationAttempt:
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
            actor_user_id=current_user.id,
            actor_username=current_user.username,
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
            actor_user_id=current_user.id,
            actor_username=current_user.username,
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
            actor_user_id=current_user.id,
            actor_username=current_user.username,
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


@router.post(
    "/{attempt_id}/execute",
    response_model=RemediationPlanResponse,
    summary="Execute an approved remediation plan",
)
def execute_remediation_endpoint(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RemediationPlanResponse:
    _require_remediation_operator(current_user)

    attempt = db.get(RemediationAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation attempt not found",
        )

    # Only approved plans that require approval, or explicitly permitted
    # low-risk plans that do not require approval, may run.
    eligible_for_execution = or_(
        and_(
            RemediationAttempt.requires_approval.is_(True),
            RemediationAttempt.status == "approved",
            RemediationAttempt.approved_by.is_not(None),
            RemediationAttempt.approved_at.is_not(None),
        ),
        and_(
            RemediationAttempt.requires_approval.is_(False),
            RemediationAttempt.status == "planned",
            RemediationAttempt.risk_level == "low",
        ),
    )

    try:
        # Atomic status claim prevents concurrent execution of the same plan.
        claim_result = db.execute(
            update(RemediationAttempt)
                .where(
                    RemediationAttempt.id == attempt_id,
                    eligible_for_execution,
                )
                .values(
                    status="executing",
                    execution_started_at=datetime.now(timezone.utc),
                    execution_finished_at=None,
                )
            )
        if claim_result.rowcount != 1:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Remediation attempt is not eligible for execution.",
                )
    

    
        record_audit_event(
            db=db,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="remediation_execution_started",
            resource_type="remediation_attempt",
            resource_id=str(attempt_id),
            details={
                "incident_id": attempt.incident_id,
                "action": attempt.action,
                "risk_level": attempt.risk_level,
                "mode": "simulated",
            },
        )
        # Commit the claim before calling the executor.
        db.commit()

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start remediation execution",
        ) from exc

    # Reload the committed attempt before invoking the executor.
    attempt = db.get(RemediationAttempt, attempt_id)

    try:
        result = execute_remediation(
            action=attempt.action,
            description=attempt.description,
            risk_level=attempt.risk_level,
        )

        attempt.status = "succeeded" if result.success else "failed"
        attempt.execution_finished_at = datetime.now(timezone.utc)
        attempt.execution_result = result.message

        audit_action = (
            "remediation_execution_succeeded"
            if result.success
            else "remediation_execution_failed"
        )
        record_audit_event(
            db=db,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action=audit_action,
            resource_type="remediation_attempt",
            resource_id=str(attempt_id),
            details={
                "incident_id": attempt.incident_id,
                "action": attempt.action,
                "mode": "simulated",
                "success": result.success,
            },
        )

        db.commit()
        db.refresh(attempt)
        return RemediationPlanResponse.model_validate(attempt)

    except Exception as exc:
        db.rollback()
        # Reload the attempt after rolling back the failed transaction.
        attempt = db.get(RemediationAttempt, attempt_id)
        if attempt is not None:
            attempt.status = "failed"
            attempt.execution_finished_at = datetime.now(timezone.utc)
            attempt.execution_result = (
                "Execution failed due to an internal error."
            )
            # Persist the failed status before attempting audit logging.
            db.commit()
        # Audit logging is best-effort and must not undo the failure status.
        try:
            record_audit_event(
                db=db,
                actor_user_id=current_user.id,
                actor_username=current_user.username,
                action="remediation_execution_failed",
                resource_type="remediation_attempt",
                resource_id=str(attempt_id),
                details={
                    "mode": "simulated",
                    "reason": "Internal execution error",
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Remediation execution failed",
        ) from exc