from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.main import app


client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "application": settings.app_name,
        "version": "0.3.0",
        "status": "running",
        "documentation": "/docs" if settings.docs_enabled else "disabled",
    }


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "enterprise-it-operations-agent",
    }


def test_readiness_endpoint() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_request_id_is_returned() -> None:
    response = client.get("/health")

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    UUID(request_id)


def test_api_documentation_is_available_in_development() -> None:
    response = client.get("/openapi.json")

    if settings.docs_enabled:
        assert response.status_code == 200
    else:
        assert response.status_code == 404


def test_invalid_log_level_is_rejected() -> None:
    try:
        Settings(log_level="INVALID")
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid log level should be rejected")


def test_api_prefix_is_normalized() -> None:
    config = Settings(api_v1_prefix="/api/v1/")
    assert config.api_v1_prefix == "/api/v1"


def test_production_rejects_sqlite() -> None:
    try:
        Settings(
            app_env="production",
            database_url="sqlite:///./data/test.db",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Production must reject SQLite")