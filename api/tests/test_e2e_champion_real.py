"""E2E evidence for the compatible real PR12 Champion output."""

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
from api.tests.test_monthly_upload_validator import csv_bytes

CHAMPION_OUTPUT_PATH = Path("runtime/functional/champion_output.json")
REAL_CHAMPION_RESULT = json.loads(CHAMPION_OUTPUT_PATH.read_text(encoding="utf-8"))
REFERENCE_MONTH = "2025-12"
REFERENCE_YEAR, REFERENCE_MONTH_NUMBER = map(int, REFERENCE_MONTH.split("-"))


def _settings(path: Path) -> Settings:
    return Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                    debug=False, cors_origins=(), db_path=str(path))


def _composition(path: Path):
    validator = MonthlyUploadValidator(max_bytes=100_000, contract=MonthlyUploadContract())
    champion_service = build_champion_service(
        "materialized",
        materialized_result_provider=CallableMaterializedChampionResultProvider(
            lambda _reference_month: REAL_CHAMPION_RESULT
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


def _post(client: TestClient):
    return client.post(
        "/api/v2/monthly-runs",
        files={"file": (
            "monthly.csv",
            csv_bytes(year=REFERENCE_YEAR, month=REFERENCE_MONTH_NUMBER),
            "text/csv",
        )},
        data={"reference_month": REFERENCE_MONTH},
    )


def _prediction_map(predictions):
    return {(item["divipola"], item["horizon"]): item for item in predictions}


def test_real_champion_completes_and_persists_predictions_and_latest(tmp_path):
    path = tmp_path / "real-champion.sqlite"
    with TestClient(_composition(path), raise_server_exceptions=False) as client:
        response = _post(client)
        assert response.status_code == 201
        body = response.json()
        run = body["run"]
        snapshot = body["prediction_snapshot"]
        assert run["status"] == "COMPLETED"
        assert run["reference_month"] == REFERENCE_MONTH
        assert snapshot["run_id"] == run["run_id"]
        assert snapshot["reference_month"] == REFERENCE_MONTH

        expected = _prediction_map(REAL_CHAMPION_RESULT["predictions"])
        assert {
            key: (item["municipality"], item["probability"], item["threshold"], item["label"])
            for key, item in expected.items()
        } == {
            ("68001", "T+1"): ("Bucaramanga", 0.7347, 0.34, "EXCESO"),
            ("68001", "T+2"): ("Bucaramanga", 0.6724, 0.27, "EXCESO"),
            ("76001", "T+1"): ("Cali", 0.0132, 0.34, "NO_EXCESO"),
            ("76001", "T+2"): ("Cali", 0.0150, 0.27, "NO_EXCESO"),
        }
        actual = _prediction_map(snapshot["predictions"])
        assert set(actual) == set(expected)
        for key, expected_item in expected.items():
            actual_item = actual[key]
            assert (
                actual_item["municipality"], actual_item["probability"],
                actual_item["decision_threshold"], actual_item["label"],
            ) == (
                expected_item["municipality"], expected_item["probability"],
                expected_item["threshold"], expected_item["label"],
            )

        latest = client.get("/api/v2/predictions/latest")
        assert latest.status_code == 200
        latest_snapshot = latest.json()["prediction_snapshot"]
        assert latest_snapshot["run_id"] == run["run_id"]
        assert len(latest_snapshot["predictions"]) == 4

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT status FROM runs").fetchall() == [("COMPLETED",)]
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 4
        for table in (
            "snapshot_quality", "current_status", "prediction_enrichments",
            "champion_enrichments",
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run["run_id"],)
            ).fetchone()[0] > 0


def test_real_artifact_and_api_contract_are_equal():
    assert REAL_CHAMPION_RESULT["feature_contract_version"] == CHAMPION_FEATURE_CONTRACT_VERSION
    assert REAL_CHAMPION_RESULT["feature_contract_sha256"] == CHAMPION_FEATURE_CONTRACT_SHA256
