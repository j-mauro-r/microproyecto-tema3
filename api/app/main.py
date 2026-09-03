"""Composition root for the BIOMAC API v2 HTTP boundary."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.api.v2.health import router as health_router
from api.app.core.config import API_PREFIX, Settings, get_settings
from api.app.core.errors import register_error_handlers
from api.app.middleware.request_id import RequestIdMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or get_settings()
    application = FastAPI(
        title="BIOMAC API",
        summary="Frontera HTTP versionada para BIOMAC",
        version=current.api_version,
        debug=current.debug,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(current.cors_origins),
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)
    application.include_router(health_router, prefix=API_PREFIX)
    return application


app = create_app()
