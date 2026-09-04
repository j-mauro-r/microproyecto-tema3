"""HU010 local E2E: real FastAPI, orchestration, materialized boundary and SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.champion.service import CallableMaterializedChampionResultProvider, build_champion_service
from api.app.core.config import Settings
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256, CHAMPION_FEATURE_CONTRACT_VERSION, CHAMPION_FEATURES,
)
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.tests.test_monthly_upload_validator import csv_bytes

REFERENCE_MONTH = "2026-01"
CONTROLLED_RESULT = {
    "model_name": "biomac-champion",
    "model_version": "hu010-controlled-contract-v1",
    "reference_month": REFERENCE_MONTH,
    "feature_contract_version": CHAMPION_FEATURE_CONTRACT_VERSION,
    "feature_contract_sha256": CHAMPION_FEATURE_CONTRACT_SHA256,
    "output_type": "probability",
    "predictions": [
        {"divipola": "68001", "municipality": "Bucaramanga", "horizon": "T+1",
         "target_month": "2026-02", "probability": 0.72, "threshold": 0.61, "label": "EXCESO"},
        {"divipola": "68001", "municipality": "Bucaramanga", "horizon": "T+2",
         "target_month": "2026-03", "probability": 0.58, "threshold": 0.67, "label": "NO_EXCESO"},
        {"divipola": "76001", "municipality": "Cali", "horizon": "T+1",
         "target_month": "2026-02", "probability": 0.43, "threshold": 0.61, "label": "NO_EXCESO"},
        {"divipola": "76001", "municipality": "Cali", "horizon": "T+2",
         "target_month": "2026-03", "probability": 0.75, "threshold": 0.67, "label": "EXCESO"},
    ],
}


@dataclass
class CountingChampionService:
    delegate: object
    calls: int = 0

    def produce(self, context):
        self.calls += 1
        return self.delegate.produce(context)


def _settings(path: Path) -> Settings:
    return Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                    debug=False, cors_origins=(), db_path=str(path))


def _composition(path: Path, resolver=lambda _: CONTROLLED_RESULT):
    service = CountingChampionService(build_champion_service(
        "materialized",
        materialized_result_provider=CallableMaterializedChampionResultProvider(resolver),
    ))
    validator = MonthlyUploadValidator(max_bytes=100_000, contract=MonthlyUploadContract())
    orchestrator = MonthlyPredictionOrchestrator(validator=validator, champion_service=service)
    persistence = MonthlyRunPersistenceService(lambda: SQLiteUnitOfWork(str(path)))
    app = create_app(_settings(path), monthly_upload_validator=validator,
                     monthly_orchestrator=orchestrator, persistence_service=persistence)
    return app, service


def _post(client: TestClient, content: bytes):
    return client.post("/api/v2/monthly-runs", files={"file": ("monthly.csv", content, "text/csv")},
                       data={"reference_month": REFERENCE_MONTH})


def _prediction_map(snapshot):
    return {(item["divipola"], item["horizon"]): item for item in snapshot["predictions"]}


def test_full_local_http_sqlite_restart_and_read_only_flow(tmp_path):
    path = tmp_path / "e2e.sqlite"
    content = csv_bytes()
    app, champion = _composition(path)
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/v2/health")
        assert health.status_code == 200
        assert health.json()["champion_ready"] is health.json()["storage_ready"] is True
        created = _post(client, content)
        assert created.status_code == 201
        body = created.json()
        assert body["run"]["status"] == "COMPLETED"
        run_id = body["run"]["run_id"]
        assert body["run"]["source_file_sha256"] == hashlib.sha256(content).hexdigest()

        with sqlite3.connect(path) as connection:
            before_reads = tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                                 for table in ("runs", "predictions"))
        latest = client.get("/api/v2/predictions/latest")
        history = client.get("/api/v2/predictions/history")
        detail = client.get(f"/api/v2/runs/{run_id}")
        assert latest.status_code == history.status_code == detail.status_code == 200
        latest_snapshot = latest.json()["prediction_snapshot"]
        assert latest_snapshot["run_id"] == run_id
        assert history.json()["items"][0]["run_id"] == run_id
        assert detail.json()["run"]["status"] == "COMPLETED"
        assert champion.calls == 1
        with sqlite3.connect(path) as connection:
            after_reads = tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                                for table in ("runs", "predictions"))
        assert after_reads == before_reads

        actual = _prediction_map(latest_snapshot)
        for expected in CONTROLLED_RESULT["predictions"]:
            item = actual[(expected["divipola"], expected["horizon"])]
            assert (item["target_month"], item["output_type"], item["probability"],
                    item["decision_threshold"], item["label"]) == (
                expected["target_month"], CONTROLLED_RESULT["output_type"],
                expected["probability"], expected["threshold"], expected["label"])

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "COMPLETED"
        assert connection.execute("SELECT COUNT(*) FROM predictions WHERE run_id=?", (run_id,)).fetchone()[0] == 4
        for table in ("snapshot_quality", "current_status", "prediction_enrichments", "champion_enrichments"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run_id,)).fetchone()[0] > 0

    restarted = create_app(_settings(path))
    with TestClient(restarted, raise_server_exceptions=False) as client:
        assert client.get("/api/v2/predictions/latest").json()["prediction_snapshot"]["run_id"] == run_id


def test_identical_post_is_idempotent_and_different_bytes_do_not_overwrite(tmp_path):
    path = tmp_path / "idempotency.sqlite"
    app, champion = _composition(path)
    content = csv_bytes()
    with TestClient(app, raise_server_exceptions=False) as client:
        first = _post(client, content).json()["run"]["run_id"]
        second = _post(client, content).json()["run"]["run_id"]
        changed = content.replace(b"1.25", b"1.26", 1)
        third = _post(client, changed).json()["run"]["run_id"]
    assert first == second and third != first and champion.calls == 3
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 8


@pytest.mark.parametrize("content", [
    csv_bytes(omit=CHAMPION_FEATURES[0]),
    csv_bytes(municipalities=("68001",)),
    csv_bytes(extra_column="objetivo"),
    csv_bytes(month=2),
    csv_bytes().replace(b"1.25", b"NaN", 1),
])
def test_invalid_uploads_stop_before_champion_and_preserve_latest(tmp_path, content):
    path = tmp_path / "invalid.sqlite"
    app, champion = _composition(path)
    with TestClient(app, raise_server_exceptions=False) as client:
        good_run = _post(client, csv_bytes()).json()["run"]["run_id"]
        failed = _post(client, content)
        latest = client.get("/api/v2/predictions/latest")
    assert failed.status_code == 422
    assert failed.json()["error"]["code"] == "INVALID_UPLOAD"
    assert latest.json()["prediction_snapshot"]["run_id"] == good_run
    assert champion.calls == 1
    assert "traceback" not in failed.text.lower() and "select " not in failed.text.lower()


def test_unavailable_champion_is_sanitized_and_preserves_previous_latest(tmp_path):
    path = tmp_path / "unavailable.sqlite"
    good_app, _ = _composition(path)
    with TestClient(good_app, raise_server_exceptions=False) as client:
        good_run = _post(client, csv_bytes()).json()["run"]["run_id"]

    bad_app, champion = _composition(path, resolver=lambda _: (_ for _ in ()).throw(FileNotFoundError("private/path")))
    with TestClient(bad_app, raise_server_exceptions=False) as client:
        failed = _post(client, csv_bytes().replace(b"1.25", b"1.26", 1))
        latest = client.get("/api/v2/predictions/latest")
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "CHAMPION_NOT_READY"
    assert "private/path" not in failed.text
    assert latest.json()["prediction_snapshot"]["run_id"] == good_run
    assert champion.calls == 1
