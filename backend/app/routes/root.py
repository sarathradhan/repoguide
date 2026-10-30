"""Root welcome route handler."""
from fastapi import APIRouter
from app.models.health import WelcomeResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["General"])


@router.get(
    "/",
    response_model=WelcomeResponse,
    summary="Application Welcome",
    description="Returns an introductory welcome message along with documentation and health check links.",
)
async def get_welcome() -> WelcomeResponse:
    """Return welcome payload."""
    info = HealthService.get_welcome_info()
    return WelcomeResponse(**info)

