"""E2E evidence that the current real PR12 output is contractually rejected."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.champion.service import CallableMaterializedChampionResultProvider, build_champion_service
from api.app.core.config import Settings
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256, CHAMPION_FEATURE_CONTRACT_VERSION,
)
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.tests.test_e2e_local import CONTROLLED_RESULT
from api.tests.test_monthly_upload_validator import csv_bytes

CHAMPION_OUTPUT_PATH = Path("runtime/functional/champion_output.json")
REAL_CHAMPION_RESULT = json.loads(CHAMPION_OUTPUT_PATH.read_text(encoding="utf-8"))
REFERENCE_MONTH = REAL_CHAMPION_RESULT["reference_month"]
REFERENCE_YEAR, REFERENCE_MONTH_NUMBER = map(int, REFERENCE_MONTH.split("-"))


def _settings(path: Path) -> Settings:
    return Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                    debug=False, cors_origins=(), db_path=str(path))


def _composition(path: Path, result: dict[str, object]):
    validator = MonthlyUploadValidator(max_bytes=100_000, contract=MonthlyUploadContract())
    champion_service = build_champion_service(
        "materialized",
        materialized_result_provider=CallableMaterializedChampionResultProvider(
            lambda _reference_month: result
        ),
    )
    app = create_app(
        _settings(path), monthly_upload_validator=validator,
        monthly_orchestrator=MonthlyPredictionOrchestrator(
            validator=validator, champion_service=champion_service
        ),
        persistence_service=MonthlyRunPersistenceService(lambda: SQLiteUnitOfWork(str(path))),
    )
    return app


def _post(client: TestClient, *, reference_month: str, year: int, month: int):
    return client.post(
        "/api/v2/monthly-runs",
        files={"file": ("monthly.csv", csv_bytes(year=year, month=month), "text/csv")},
        data={"reference_month": reference_month},
    )


def test_real_champion_contract_mismatch_is_explicit_and_returns_422(tmp_path):
    path = tmp_path / "real-mismatch.sqlite"
    with TestClient(_composition(path, REAL_CHAMPION_RESULT), raise_server_exceptions=False) as client:
        response = _post(client, reference_month=REFERENCE_MONTH, year=REFERENCE_YEAR,
                         month=REFERENCE_MONTH_NUMBER)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "CHAMPION_INPUT_INVALID"
    assert error["stage"] == "INFERENCING"
    assert error["details"] == {
        "reason": "feature_contract_mismatch",
        "expected_version": CHAMPION_FEATURE_CONTRACT_VERSION,
        "received_version": REAL_CHAMPION_RESULT["feature_contract_version"],
        "expected_sha256": CHAMPION_FEATURE_CONTRACT_SHA256,
        "received_sha256": REAL_CHAMPION_RESULT["feature_contract_sha256"],
    }


def test_real_mismatch_persists_failed_run_without_predictions_or_snapshot(tmp_path):
    path = tmp_path / "failed-run.sqlite"
    with TestClient(_composition(path, REAL_CHAMPION_RESULT), raise_server_exceptions=False) as client:
        response = _post(client, reference_month=REFERENCE_MONTH, year=REFERENCE_YEAR,
                         month=REFERENCE_MONTH_NUMBER)
        latest = client.get("/api/v2/predictions/latest")

    assert response.status_code == 422
    assert latest.status_code == 404
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT status FROM runs").fetchall() == [("FAILED",)]
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0


def test_real_mismatch_preserves_previous_completed_latest(tmp_path):
    path = tmp_path / "preserve-latest.sqlite"
    controlled_month = CONTROLLED_RESULT["reference_month"]
    controlled_year, controlled_month_number = map(int, controlled_month.split("-"))
    with TestClient(_composition(path, CONTROLLED_RESULT), raise_server_exceptions=False) as client:
        completed = _post(client, reference_month=controlled_month, year=controlled_year,
                          month=controlled_month_number)
        completed_run_id = completed.json()["run"]["run_id"]

    with TestClient(_composition(path, REAL_CHAMPION_RESULT), raise_server_exceptions=False) as client:
        rejected = _post(client, reference_month=REFERENCE_MONTH, year=REFERENCE_YEAR,
                         month=REFERENCE_MONTH_NUMBER)
        latest = client.get("/api/v2/predictions/latest")

    assert completed.status_code == 201
    assert rejected.status_code == 422
    assert latest.status_code == 200
    assert latest.json()["prediction_snapshot"]["run_id"] == completed_run_id
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM runs WHERE status='COMPLETED'"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 4


def test_real_artifact_and_api_contract_are_demonstrably_different():
    assert REAL_CHAMPION_RESULT["feature_contract_version"] != CHAMPION_FEATURE_CONTRACT_VERSION
    assert REAL_CHAMPION_RESULT["feature_contract_sha256"] != CHAMPION_FEATURE_CONTRACT_SHA256
