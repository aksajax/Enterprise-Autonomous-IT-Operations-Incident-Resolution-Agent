import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.routes.health import router as health_router
from app.api.routes.incidents import router as incidents_router
from app.core.config import settings
from app.core.logging_config import configure_logging

from app.api.routes.auth import router as auth_router
from app.api.routes.metrics import router as metrics_router

from app.api.routes.remediation import router as remediation_router

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_starting",
        extra={"environment": settings.app_env},
    )
    yield
    logger.info("application_stopping")


app = FastAPI(
    title=settings.app_name,
    description=(
        "An enterprise platform for infrastructure monitoring, "
        "incident investigation, controlled remediation, and verification."
    ),
    version="0.3.0",
    debug=False,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        response = JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred.",
                "request_id": request_id,
            },
        )

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
        },
    )

    return response

app.include_router(metrics_router, prefix=settings.api_v1_prefix)
app.include_router(health_router)
app.include_router(
    incidents_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    remediation_router,
    prefix=settings.api_v1_prefix,
)

@app.get("/", tags=["Root"], summary="Application information")
async def root() -> dict[str, str]:
    return {
        "application": settings.app_name,
        "version": app.version,
        "status": "running",
        "documentation": "/docs" if settings.docs_enabled else "disabled",
    }


@app.get("/ready", tags=["Health"], summary="Check process readiness")
async def readiness_check() -> dict[str, str]:
    return {
        "status": "ready",
        "environment": settings.app_env,
    }