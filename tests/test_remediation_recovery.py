from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import RemediationAttempt
from app.services.remediation_recovery import (
    RECOVERY_FAILURE_MESSAGE,
    recover_stuck_executions,
)


def test_recover_stuck_executions_marks_old_attempt_failed(
    db_session,
):
    old_attempt = RemediationAttempt(
        incident_id="INC-123",
        action="restart_service",
        description="Test remediation action",
        risk_level="low",
        status="executing",
        execution_started_at=(
            datetime.now(timezone.utc) - timedelta(minutes=20)
        ),
    )
    db_session.add(old_attempt)
    db_session.commit()

    recovered = recover_stuck_executions(
        db_session,
        timeout_minutes=15,
    )

    db_session.refresh(old_attempt)

    assert recovered == 1
    assert old_attempt.status == "failed"
    assert old_attempt.execution_finished_at is not None
    assert old_attempt.execution_result == RECOVERY_FAILURE_MESSAGE


def test_recover_stuck_executions_ignores_recent_attempt(
    db_session,
):
    recent_attempt = RemediationAttempt(
        incident_id="INC-123",
        action="restart_service",
        description="Test remediation action",
        risk_level="low",
        status="executing",
        execution_started_at=(
            datetime.now(timezone.utc) - timedelta(minutes=2)
        ),
    )
    db_session.add(recent_attempt)
    db_session.commit()

    recovered = recover_stuck_executions(
        db_session,
        timeout_minutes=15,
    )

    db_session.refresh(recent_attempt)

    assert recovered == 0
    assert recent_attempt.status == "executing"


def test_recover_stuck_executions_rejects_invalid_timeout(
    db_session,
):
    with pytest.raises(ValueError):
        recover_stuck_executions(db_session, timeout_minutes=0)