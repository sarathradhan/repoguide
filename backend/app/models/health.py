"""Schemas for health and root endpoints."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing backend health status."""

    status: str = Field(..., description="Service health state, e.g. healthy")
    service: str = Field(..., description="Name of the service")
    version: str = Field(..., description="Current semantic version")
    environment: str = Field(..., description="Active runtime environment")
    timestamp: datetime = Field(..., description="UTC server timestamp")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")


class WelcomeResponse(BaseModel):
    """Schema representing root welcome response."""

    message: str = Field(..., description="Welcome greeting message")
    app: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    status: str = Field(..., description="Service status")
    docs_url: str = Field(..., description="Interactive API documentation URL")
    health_endpoint: str = Field(..., description="Health check endpoint URL")


class ErrorResponse(BaseModel):
    """Standardized API error response format."""

    error: str = Field(..., description="Short error name or status code")
    detail: str = Field(..., description="Detailed message about the error")
    timestamp: datetime = Field(..., description="UTC error timestamp")
    path: Optional[str] = Field(None, description="Request path that generated the error")

