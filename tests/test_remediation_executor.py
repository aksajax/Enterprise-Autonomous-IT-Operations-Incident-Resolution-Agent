
import pytest

from app.services.remediation_executor import (
    DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    execute_remediation,
)


def test_simulated_execution_succeeds():
    result = execute_remediation(
        action="restart_service",
        description="Restart an unhealthy service",
        risk_level="low",
    )

    assert result.success is True
    assert "SIMULATED" in result.message
    assert "No infrastructure changes were made." in result.message


def test_execution_timeout_must_be_positive():
    with pytest.raises(ValueError, match="timeout_seconds"):
        execute_remediation(
            action="restart_service",
            description="Restart an unhealthy service",
            risk_level="low",
            timeout_seconds=0,
        )


def test_default_execution_timeout_is_configured():
    assert DEFAULT_EXECUTION_TIMEOUT_SECONDS == 30
