"""Liveness endpoint for the HTTP boundary."""

from fastapi import APIRouter

from api.app.core.config import get_settings
from api.app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        api_version=settings.api_version,
        champion_ready=False,
        storage_ready=False,
    )
