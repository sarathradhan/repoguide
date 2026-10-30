"""API route definitions package."""
from .root import router as root_router
from .health import router as health_router

__all__ = ["root_router", "health_router"]

