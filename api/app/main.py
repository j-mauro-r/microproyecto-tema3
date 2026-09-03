"""Composition root for the BIOMAC API v2 HTTP boundary."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.api.v2.health import router as health_router
from api.app.api.v2.monthly_runs import router as monthly_runs_router
from api.app.core.config import API_PREFIX, Settings, get_settings
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.app.core.errors import register_error_handlers
from api.app.middleware.request_id import RequestIdMiddleware


def create_app(
    settings: Settings | None = None,
    monthly_upload_validator: MonthlyUploadValidator | None = None,
    monthly_orchestrator: MonthlyPredictionOrchestrator | None = None,
    persistence_service: MonthlyRunPersistenceService | None = None,
) -> FastAPI:
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
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)
    application.state.monthly_upload_validator = monthly_upload_validator or MonthlyUploadValidator(
        max_bytes=current.upload_max_bytes,
        contract=MonthlyUploadContract(
            allowed_extensions=current.upload_allowed_extensions,
        ),
    )
    application.state.monthly_orchestrator = monthly_orchestrator
    application.state.monthly_run_persistence = persistence_service or (
        MonthlyRunPersistenceService(lambda: SQLiteUnitOfWork(current.db_path))
        if monthly_orchestrator is not None
        else None
    )
    application.include_router(health_router, prefix=API_PREFIX)
    application.include_router(monthly_runs_router, prefix=API_PREFIX)
    return application


app = create_app()
