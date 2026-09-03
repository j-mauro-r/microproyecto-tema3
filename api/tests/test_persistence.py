from dataclasses import replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import inspect
import sqlite3
import subprocess
import sys

import pytest

from api.app.champion.models import ChampionMetadata
from api.app.domain.errors import ContractError
from api.app.orchestration.monthly import (
    CandidatePrediction, MonthlyRunResult, PredictionSnapshotCandidate,
    build_idempotency_key,
)
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def _ready(*, run_id="run-1", source_hash="hash-a", version="v1", duplicate=False):
    champion = ChampionMetadata(
        name="biomac-champion", version=version, supported_horizons=("T+1", "T+2"),
        output_type="probability", feature_contract_version="contract-v1",
        feature_contract_sha256="contract-sha",
    )
    predictions = tuple(
        CandidatePrediction(
            divipola=code, municipality=name, horizon=horizon,
            target_month="2026-02" if horizon == "T+1" else "2026-03",
            output_type="probability", probability=None if code == "76001" else 0.72,
            expected_cases=None, risk_score=None,
            label=None if code == "76001" else "EXCESO",
            decision_threshold=0.61 if horizon == "T+1" else 0.67,
        )
        for code, name in (("68001", "Bucaramanga"), ("76001", "Cali"))
        for horizon in ("T+1", "T+2")
    )
    if duplicate:
        predictions += (predictions[0],)
    snapshot = PredictionSnapshotCandidate(
        run_id=run_id, generated_at=NOW + timedelta(seconds=1), reference_month="2026-01",
        source_file_sha256=source_hash, champion=champion, predictions=predictions,
    )
    return MonthlyRunResult(
        run_id=run_id, request_id="request-1", status=RunStatus.READY_TO_PERSIST,
        stages=(RunStatus.RECEIVED, RunStatus.READY_TO_PERSIST),
        reference_month="2026-01", source_file_sha256=source_hash,
        idempotency_key=build_idempotency_key("2026-01", source_hash, version),
        champion_version=version, created_at=NOW, finished_at=NOW + timedelta(seconds=2),
        snapshot=snapshot, error_code=None, error_stage=None, error_message=None,
    )


def _service(path):
    return MonthlyRunPersistenceService(
        lambda: SQLiteUnitOfWork(str(path)), clock=lambda: NOW + timedelta(seconds=3)
    )


def _counts(path):
    with sqlite3.connect(path) as connection:
        return tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("runs", "predictions"))


def test_database_schema_initialization_is_created_idempotent_and_enables_foreign_keys(tmp_path):
    path = tmp_path / "biomac.sqlite"
    first = SQLiteUnitOfWork(str(path))
    second = SQLiteUnitOfWork(str(path))
    assert path.exists() and first.foreign_keys_enabled() and second.foreign_keys_enabled()
    with sqlite3.connect(path) as connection:
        assert {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )} >= {"runs", "predictions"}


def test_ready_result_is_atomically_completed_and_recoverable(tmp_path):
    service = _service(tmp_path / "biomac.db")
    completed = service.persist(_ready())
    recovered = service.get("run-1")
    snapshot = service.get_snapshot("run-1")
    assert completed.status is RunStatus.COMPLETED
    assert completed.stages[-2:] == (RunStatus.PERSISTING, RunStatus.COMPLETED)
    assert completed.completed_at == NOW + timedelta(seconds=3)
    assert recovered == completed and snapshot == completed.snapshot
    assert len(snapshot.predictions) == 4
    assert [item.decision_threshold for item in snapshot.predictions] == [0.61, 0.67, 0.61, 0.67]
    assert snapshot.predictions[2].probability is None


def test_identical_retry_returns_durable_result_without_duplicates(tmp_path):
    path = tmp_path / "biomac.db"
    service = _service(path)
    first = service.persist(_ready())
    second = service.persist(_ready(run_id="run-retry"))
    assert second.run_id == first.run_id == "run-1"
    assert _counts(path) == (1, 4)


def test_competing_identical_attempts_resolve_to_one_completed_run(tmp_path):
    path = tmp_path / "biomac.db"
    SQLiteUnitOfWork(str(path))
    candidates = (_ready(run_id="run-a"), _ready(run_id="run-b"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        completed = list(pool.map(lambda item: _service(path).persist(item), candidates))
    assert completed[0].run_id == completed[1].run_id
    assert all(item.status is RunStatus.COMPLETED for item in completed)
    assert _counts(path) == (1, 4)


@pytest.mark.parametrize("changed", ["hash", "champion"])
def test_hash_or_champion_change_allows_new_run(tmp_path, changed):
    path = tmp_path / "biomac.db"
    service = _service(path)
    service.persist(_ready())
    candidate = (_ready(run_id="run-2", source_hash="hash-b") if changed == "hash"
                 else _ready(run_id="run-2", version="v2"))
    assert service.persist(candidate).run_id == "run-2"
    assert _counts(path) == (2, 8)


def test_prediction_constraint_failure_rolls_back_and_preserves_previous_completed(tmp_path):
    path = tmp_path / "biomac.db"
    service = _service(path)
    previous = service.persist(_ready())
    with pytest.raises(ContractError) as raised:
        service.persist(_ready(run_id="run-bad", source_hash="hash-b", duplicate=True))
    assert raised.value.code is ErrorCode.PERSISTENCE_FAILED
    assert raised.value.stage is RunStatus.PERSISTING
    assert service.get("run-bad") is None
    assert service.get("run-1") == previous
    assert _counts(path) == (1, 4)


def test_failed_run_is_traced_without_snapshot(tmp_path):
    service = _service(tmp_path / "biomac.db")
    failed = replace(
        _ready(), status=RunStatus.FAILED, stages=(RunStatus.RECEIVED, RunStatus.FAILED),
        snapshot=None, idempotency_key=None, error_code=ErrorCode.MAPPING_FAILED,
        error_stage=RunStatus.MAPPING, error_message="Salida rechazada.",
    )
    persisted = service.persist(failed)
    assert persisted.status is RunStatus.FAILED
    assert persisted.error_code is ErrorCode.MAPPING_FAILED
    assert service.get_snapshot(failed.run_id) is None


def test_second_service_instance_recovers_run_and_snapshot(tmp_path):
    path = tmp_path / "biomac.db"
    stored = _service(path).persist(_ready())
    recovered = _service(path).get(stored.run_id)
    assert recovered == stored and recovered.snapshot is not None


def test_database_constraints_reject_orphan_and_duplicate_prediction(tmp_path):
    path = tmp_path / "biomac.db"
    uow = SQLiteUnitOfWork(str(path))
    with pytest.raises(sqlite3.IntegrityError), uow:
        uow.connection.execute(
            "INSERT INTO predictions (run_id, divipola, municipality, horizon, target_month, "
            "output_type, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("missing", "68001", "Bucaramanga", "T+1", "2026-02", "probability", NOW.isoformat()),
        )
    service = _service(path)
    service.persist(_ready())
    with sqlite3.connect(path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO predictions (run_id, divipola, municipality, horizon, target_month, "
            "output_type, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "68001", "Bucaramanga", "T+1", "2026-02", "probability", NOW.isoformat()),
        )


def test_hu005_and_http_boundary_have_no_sqlite_or_sql():
    import api.app.api.v2.monthly_runs as http_module
    import api.app.orchestration.monthly as orchestration_module
    for module in (http_module, orchestration_module):
        source = inspect.getsource(module).lower()
        assert "sqlite3" not in source and "select " not in source and "insert " not in source


def test_no_cloud_or_ml_runtime_dependency_is_loaded():
    script = """
import json, sys
import api.app.persistence.service
import api.app.persistence.sqlite
forbidden = ('boto3', 'dvc', 'mlflow', 'supabase')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "[]"


def test_runtime_database_patterns_are_gitignored(tmp_path):
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    ).stdout.strip()
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "runtime/probe.db", "runtime/probe.db-wal",
         "runtime/probe.db-shm", "runtime/probe.sqlite", "runtime/probe.sqlite3"],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    assert len(result.stdout.splitlines()) == 5
