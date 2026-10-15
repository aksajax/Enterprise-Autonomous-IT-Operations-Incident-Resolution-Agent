
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.main as main


def test_startup_runs_remediation_recovery(monkeypatch):
    recovery = MagicMock(return_value=2)
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = MagicMock()

    monkeypatch.setattr(
        main,
        "recover_stuck_executions",
        recovery,
    )
    monkeypatch.setattr(
        main,
        "SessionLocal",
        session_factory,
    )

    with TestClient(main.app):
        pass

    recovery.assert_called_once()
    assert recovery.call_args.kwargs["timeout_minutes"] == 15
