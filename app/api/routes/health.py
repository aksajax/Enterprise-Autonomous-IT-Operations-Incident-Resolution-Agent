from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Check application health")
async def health_check() -> dict[str, str]:
    """Return the current application's basic health status."""
    return {
        "status": "healthy",
        "service": "enterprise-it-operations-agent",
    }