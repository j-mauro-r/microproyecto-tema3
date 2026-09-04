from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.main import create_app
from api.app.orchestration.monthly import build_idempotency_key
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus
from api.tests.test_persistence import _ready


def _settings(path):
    return Settings(
        service_name="biomac-api", api_version="2.0.0", environment="test",
        debug=False, cors_origins=(), db_path=str(path),
    )


def _candidate(month, run_id, source_hash):
    result = _ready(run_id=run_id, source_hash=source_hash)
    snapshot = replace(result.snapshot, reference_month=month, source_file_sha256=source_hash)
    return replace(
        result, reference_month=month, source_file_sha256=source_hash, snapshot=snapshot,
        idempotency_key=build_idempotency_key(month, source_hash, result.champion_version),
    )


def _persist(path, result, completed_at):
    service = MonthlyRunPersistenceService(
        lambda: SQLiteUnitOfWork(str(path)), clock=lambda: completed_at
    )
    return service.persist(result)


def _seed(path):
    first = _persist(path, _candidate("2026-01", "run-a", "hash-a"),
                     datetime(2026, 2, 1, tzinfo=timezone.utc))
    second_candidate = _candidate("2026-02", "run-b", "hash-b")
    enriched = tuple(
        replace(item, probability=None, expected_cases=12.5, risk_score=0.8, label=None)
        if item.divipola == "76001" else item
        for item in second_candidate.snapshot.predictions
    )
    second_candidate = replace(
        second_candidate, snapshot=replace(second_candidate.snapshot, predictions=enriched)
    )
    second = _persist(path, second_candidate, datetime(2026, 3, 1, tzinfo=timezone.utc))
    failed = replace(
        _candidate("2026-03", "run-failed", "hash-f"), status=RunStatus.FAILED,
        stages=(RunStatus.RECEIVED, RunStatus.FAILED), snapshot=None,
        idempotency_key=None, error_code=ErrorCode.INFERENCE_FAILED,
        error_stage=RunStatus.INFERENCING, error_message="Inferencia no disponible.",
    )
    _persist(path, failed, datetime(2026, 4, 1, tzinfo=timezone.utc))
    return first, second


@pytest.fixture
def read_client(tmp_path):
    path = tmp_path / "read.sqlite"
    completed = _seed(path)
    with TestClient(create_app(_settings(path)), raise_server_exceptions=False) as client:
        yield client, path, completed


def test_get_run_recovers_completed_and_failed(read_client):
    client, _, _ = read_client
    completed = client.get("/api/v2/runs/run-b")
    failed = client.get("/api/v2/runs/run-failed")
    assert completed.status_code == failed.status_code == 200
    assert completed.json()["run"]["status"] == "COMPLETED"
    error = failed.json()["run"]["error"]
    assert error == {"code": "INFERENCE_FAILED", "stage": "INFERENCING",
                     "message": "Inferencia no disponible."}


def test_get_missing_run_returns_stable_404(read_client):
    response = read_client[0].get("/api/v2/runs/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_latest_uses_newest_completed_and_ignores_newer_failed(read_client):
    response = read_client[0].get("/api/v2/predictions/latest")
    body = response.json()["prediction_snapshot"]
    assert response.status_code == 200 and body["run_id"] == "run-b"
    assert {item["divipola"] for item in body["predictions"]} == {"68001", "76001"}
    assert {item["horizon"] for item in body["predictions"]} == {"T+1", "T+2"}


@pytest.mark.parametrize("code", ["68001", "76001"])
def test_latest_filters_each_municipality(read_client, code):
    response = read_client[0].get(
        "/api/v2/predictions/latest", params={"municipality_codes": code}
    )
    assert {item["divipola"] for item in response.json()["prediction_snapshot"]["predictions"]} == {code}


@pytest.mark.parametrize("horizon", ["T+1", "T+2"])
def test_latest_filters_each_horizon_and_preserves_threshold(read_client, horizon):
    response = read_client[0].get(
        "/api/v2/predictions/latest", params={"horizons": horizon}
    )
    predictions = response.json()["prediction_snapshot"]["predictions"]
    expected = 0.61 if horizon == "T+1" else 0.67
    assert {item["horizon"] for item in predictions} == {horizon}
    assert {item["decision_threshold"] for item in predictions} == {expected}


def test_latest_empty_returns_prediction_not_found(tmp_path):
    path = tmp_path / "empty.sqlite"
    SQLiteUnitOfWork(str(path))
    with TestClient(create_app(_settings(path)), raise_server_exceptions=False) as client:
        response = client.get("/api/v2/predictions/latest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PREDICTION_NOT_FOUND"


def test_latest_uses_run_id_as_deterministic_tiebreaker(tmp_path):
    path = tmp_path / "tie.sqlite"
    completed_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    _persist(path, _candidate("2026-02", "run-a", "hash-a"), completed_at)
    _persist(path, _candidate("2026-02", "run-z", "hash-z"), completed_at)
    with TestClient(create_app(_settings(path)), raise_server_exceptions=False) as client:
        response = client.get("/api/v2/predictions/latest")
    assert response.json()["prediction_snapshot"]["run_id"] == "run-z"


def test_nullable_and_non_probability_outputs_are_preserved(read_client):
    body = read_client[0].get(
        "/api/v2/predictions/latest", params={"municipality_codes": "76001"}
    ).json()["prediction_snapshot"]
    assert all(item["probability"] is None for item in body["predictions"])
    assert all(item["expected_cases"] == 12.5 and item["risk_score"] == 0.8
               for item in body["predictions"])


def test_history_contains_only_completed_in_descending_order(read_client):
    response = read_client[0].get("/api/v2/predictions/history")
    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()["items"]] == ["run-b", "run-a"]
    assert response.json()["pagination"] == {"limit": 20, "offset": 0, "returned": 2}


@pytest.mark.parametrize(
    ("params", "expected"),
    [({"from_month": "2026-02"}, ["run-b"]),
     ({"to_month": "2026-01"}, ["run-a"]),
     ({"municipality_codes": "68001"}, ["run-b", "run-a"]),
     ({"horizon": "T+2"}, ["run-b", "run-a"]),
     ({"limit": "1"}, ["run-b"]),
     ({"limit": "1", "offset": "1"}, ["run-a"])],
)
def test_history_filters_and_pagination(read_client, params, expected):
    body = read_client[0].get("/api/v2/predictions/history", params=params).json()
    assert [item["run_id"] for item in body["items"]] == expected
    if "municipality_codes" in params:
        assert all(prediction["divipola"] == "68001" for item in body["items"]
                   for prediction in item["predictions"])
    if "horizon" in params:
        assert all(prediction["horizon"] == "T+2" for item in body["items"]
                   for prediction in item["predictions"])


def test_empty_history_is_200_with_empty_items(read_client):
    response = read_client[0].get(
        "/api/v2/predictions/history", params={"from_month": "2030-01"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == [] and response.json()["pagination"]["returned"] == 0


@pytest.mark.parametrize(
    ("path", "reason"),
    [("/api/v2/predictions/latest?municipality_codes=99999", "municipality_codes_invalid"),
     ("/api/v2/predictions/latest?horizons=T%2B3", "horizons_invalid"),
     ("/api/v2/predictions/history?horizon=T%2B3", "horizon_invalid"),
     ("/api/v2/predictions/history?from_month=2026-13", "from_month_invalid"),
     ("/api/v2/predictions/history?from_month=2026-03&to_month=2026-01", "month_range_invalid"),
     ("/api/v2/predictions/history?limit=0", "limit_invalid"),
     ("/api/v2/predictions/history?offset=-1", "offset_invalid"),
     ("/api/v2/predictions/history?limit=many", "pagination_invalid")],
)
def test_invalid_filters_return_400_invalid_request(read_client, path, reason):
    response = read_client[0].get(path)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.json()["error"]["details"]["reason"] == reason


def test_get_requests_do_not_call_inference_or_modify_sqlite(read_client):
    client, path, _ = read_client
    class Exploding:
        calls = 0
        def run(self, *_):
            self.calls += 1
            raise AssertionError("orchestrator called")
        def produce(self, *_):
            self.calls += 1
            raise AssertionError("champion called")

    spy = Exploding()
    client.app.state.monthly_orchestrator = spy
    client.app.state.champion_service = spy
    with sqlite3.connect(path) as connection:
        before = connection.execute(
            "SELECT run_id, status FROM runs ORDER BY run_id"
        ).fetchall(), connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert client.get("/api/v2/runs/run-b").status_code == 200
    assert client.get("/api/v2/predictions/latest").status_code == 200
    assert client.get("/api/v2/predictions/history").status_code == 200
    with sqlite3.connect(path) as connection:
        after = connection.execute(
            "SELECT run_id, status FROM runs ORDER BY run_id"
        ).fetchall(), connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert spy.calls == 0 and after == before


def test_query_import_path_does_not_load_ml_or_cloud_dependencies():
    script = """
import json, sys
import api.app.api.v2.queries
import api.app.query.service
import api.app.persistence.sqlite
forbidden = ('xgboost', 'lightgbm', 'mlflow', 'dvc', 'boto3')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run([sys.executable, "-c", script], check=True,
                            capture_output=True, text=True)
    assert json.loads(result.stdout) == []


def test_real_storage_failure_is_sanitized(tmp_path):
    missing = tmp_path / "missing.sqlite"
    with TestClient(create_app(_settings(missing)), raise_server_exceptions=False) as client:
        response = client.get("/api/v2/predictions/latest")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "PERSISTENCE_FAILED"
    assert str(tmp_path) not in response.text and "SELECT" not in response.text
