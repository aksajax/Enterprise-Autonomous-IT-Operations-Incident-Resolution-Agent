
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RemediationAttempt


RECOVERY_FAILURE_MESSAGE = (
    "Execution interrupted or timed out. "
    "Verify infrastructure state before retrying."
)


def recover_stuck_executions(
    db: Session,
    timeout_minutes: int = 15,
) -> int:
    """
    Mark stale remediation executions as failed.

    Returns:
        Number of remediation attempts recovered.

    Important:
        This function never retries remediation automatically.
        Infrastructure state must be verified before retrying.
    """
    if timeout_minutes <= 0:
        raise ValueError("timeout_minutes must be greater than zero.")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=timeout_minutes)

    statement = select(RemediationAttempt).where(
        RemediationAttempt.status == "executing",
        RemediationAttempt.execution_started_at.is_not(None),
        RemediationAttempt.execution_started_at < cutoff,
    )

    attempts = db.scalars(statement).all()

    recovered_count = 0

    try:
        for attempt in attempts:
            # Recheck the state in case it changed after selection.
            if attempt.status != "executing":
                continue

            attempt.status = "failed"
            attempt.execution_finished_at = now
            attempt.execution_result = RECOVERY_FAILURE_MESSAGE

            recovered_count += 1

        if recovered_count:
            db.commit()

        return recovered_count

    except Exception:
        db.rollback()
        raise
