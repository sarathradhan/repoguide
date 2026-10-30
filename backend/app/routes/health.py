"""Health check route handler."""
from fastapi import APIRouter
from app.models.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/api", tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns backend operational status, uptime, environment, and current timestamp.",
)
async def check_health() -> HealthResponse:
    """Return current backend health status."""
    health_data = HealthService.get_health_status()
    return HealthResponse(**health_data)

