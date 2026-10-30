"""Service responsible for system health and status reporting."""
from datetime import datetime, timezone
from app.core.config import settings

# Record the startup timestamp
_START_TIME: datetime = datetime.now(timezone.utc)


class HealthService:
    """Service to handle health checks and welcome diagnostics."""

    @staticmethod
    def get_health_status() -> dict:
        """Calculate and return system health diagnostic information."""
        now = datetime.now(timezone.utc)
        uptime = (now - _START_TIME).total_seconds()
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "timestamp": now,
            "uptime_seconds": round(uptime, 2),
        }

    @staticmethod
    def get_welcome_info() -> dict:
        """Return welcome overview with available endpoints."""
        return {
            "message": f"Welcome to {settings.APP_NAME} API - Your AI GitHub Repository Guide",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
            "docs_url": "/docs",
            "health_endpoint": "/api/health",
        }

