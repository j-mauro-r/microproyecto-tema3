"""Explicit local-only composition for the BIOMAC functional HTTP test."""

from __future__ import annotations

import json
import os
from pathlib import Path

from api.app.champion.service import (
    CallableMaterializedChampionResultProvider,
    build_champion_service,
)
from api.app.core.config import get_settings
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork


def create_functional_app():
    """Compose the real local stack from explicitly configured runtime artifacts."""

    settings = get_settings()
    champion_path = Path(
        os.getenv(
            "BIOMAC_FUNCTIONAL_CHAMPION_OUTPUT",
            "runtime/functional/champion_output.json",
        )
    )
    champion_result = json.loads(champion_path.read_text(encoding="utf-8"))
    champion_service = build_champion_service(
        "materialized",
        materialized_result_provider=CallableMaterializedChampionResultProvider(
            lambda _reference_month: champion_result
        ),
    )
    validator = MonthlyUploadValidator(
        max_bytes=settings.upload_max_bytes,
        contract=MonthlyUploadContract(
            allowed_extensions=settings.upload_allowed_extensions,
        ),
    )
    orchestrator = MonthlyPredictionOrchestrator(
        validator=validator,
        champion_service=champion_service,
    )
    persistence = MonthlyRunPersistenceService(
        lambda: SQLiteUnitOfWork(settings.db_path)
    )
    return create_app(
        settings,
        monthly_upload_validator=validator,
        monthly_orchestrator=orchestrator,
        persistence_service=persistence,
    )


app = create_functional_app()
