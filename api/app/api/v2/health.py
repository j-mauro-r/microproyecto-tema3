"""Liveness endpoint for the HTTP boundary."""

from fastapi import APIRouter, Request

from api.app.core.config import get_settings
from api.app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        api_version=settings.api_version,
        champion_ready=request.app.state.monthly_orchestrator is not None,
        storage_ready=request.app.state.monthly_run_persistence is not None,
    )
