from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import inspect
import json
import subprocess
import sys

import pytest

from api.app.champion.models import ChampionMetadata, ChampionOutput, ChampionPrediction
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.orchestration.monthly import (
    MonthlyPredictionOrchestrator,
    MonthlyRunCommand,
    PredictionSnapshotCandidate,
    ResultMapper,
    build_idempotency_key,
)
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus
from api.tests.test_monthly_upload_validator import csv_bytes


class StepClock:
    def __init__(self):
        self.current = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def metadata(version="champion-v1", horizons=("T+1", "T+2")):
    return ChampionMetadata(
        name="biomac-champion",
        version=version,
        supported_horizons=horizons,
        output_type="probability",
        feature_contract_version="contract-v1",
        feature_contract_sha256="contract-sha",
    )


def champion_output(*, probabilities=True, horizons=("T+1", "T+2")):
    thresholds = {"T+1": 0.61, "T+2": 0.67}
    predictions = tuple(
        ChampionPrediction(
            divipola=code,
            municipality=name,
            horizon=horizon,
            target_month="2026-02" if horizon == "T+1" else "2026-03",
            output_type="probability" if probabilities else "expected_cases",
            probability=(0.72 if code == "68001" else 0.42) if probabilities else None,
            expected_cases=None if probabilities else 12.0,
            label=("EXCESO" if code == "68001" else "NO_EXCESO") if probabilities else None,
            decision_threshold=thresholds[horizon] if probabilities else None,
        )
        for code, name in (("68001", "Bucaramanga"), ("76001", "Cali"))
        for horizon in horizons
    )
    return ChampionOutput(
        reference_month="2026-01",
        predictions=predictions,
        metadata=replace(
            metadata(horizons=horizons),
            output_type="probability" if probabilities else "expected_cases",
        ),
        source_file_sha256=None,
    )


class FakeChampionService:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    def produce(self, context):
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        return replace(self.output, source_file_sha256=context.source_file_sha256)


class SpyMapper(ResultMapper):
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def map(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return super().map(**kwargs)


@pytest.fixture
def validator():
    return MonthlyUploadValidator(max_bytes=64 * 1024, contract=MonthlyUploadContract())


@pytest.fixture
def command():
    return MonthlyRunCommand(
        reference_month="2026-01",
        source_file_name="monthly.csv",
        source_bytes=csv_bytes(),
        request_id="request-123",
    )


def orchestrator(validator, service, mapper=None):
    return MonthlyPredictionOrchestrator(
        validator=validator,
        champion_service=service,
        result_mapper=mapper,
        clock=StepClock(),
        run_id_factory=lambda month: f"run-{month}-fixed",
    )


def test_successful_flow_is_ready_to_persist_and_traced(validator, command):
    service = FakeChampionService(champion_output())
    result = orchestrator(validator, service).run(command)
    assert result.run_id == "run-2026-01-fixed"
    assert result.request_id == "request-123"
    assert result.status == RunStatus.READY_TO_PERSIST
    assert result.stages == (
        RunStatus.RECEIVED,
        RunStatus.VALIDATING,
        RunStatus.PREPARING,
        RunStatus.INFERENCING,
        RunStatus.MAPPING,
        RunStatus.READY_TO_PERSIST,
    )
    assert result.created_at < result.snapshot.generated_at < result.finished_at
    assert service.calls[0].reference_month == "2026-01"
    assert service.calls[0].validated_upload is not None
    assert len(service.calls) == 1
    with pytest.raises(FrozenInstanceError):
        result.status = RunStatus.COMPLETED


def test_result_mapper_preserves_real_outputs_without_enrichment(validator, command):
    result = orchestrator(validator, FakeChampionService(champion_output())).run(command)
    assert isinstance(result.snapshot, PredictionSnapshotCandidate)
    assert [(p.divipola, p.municipality, p.horizon) for p in result.snapshot.predictions] == [
        ("68001", "Bucaramanga", "T+1"),
        ("68001", "Bucaramanga", "T+2"),
        ("76001", "Cali", "T+1"),
        ("76001", "Cali", "T+2"),
    ]
    assert [p.decision_threshold for p in result.snapshot.predictions] == [0.61, 0.67, 0.61, 0.67]
    assert result.snapshot.champion.version == "champion-v1"
    assert result.snapshot.champion.feature_contract_sha256 == "contract-sha"


def test_mapper_does_not_fabricate_probability_or_horizons(validator, command):
    result = orchestrator(
        validator,
        FakeChampionService(champion_output(probabilities=False, horizons=("T+1",))),
    ).run(command)
    assert len(result.snapshot.predictions) == 2
    assert all(p.horizon == "T+1" for p in result.snapshot.predictions)
    assert all(p.probability is None for p in result.snapshot.predictions)
    assert all(p.expected_cases == 12.0 for p in result.snapshot.predictions)
    assert all(p.decision_threshold is None for p in result.snapshot.predictions)


def test_idempotency_key_is_deterministic_and_sensitive_to_each_component():
    baseline = build_idempotency_key("2026-01", "hash-a", "v1")
    assert baseline == build_idempotency_key("2026-01", "hash-a", "v1")
    assert baseline != build_idempotency_key("2026-02", "hash-a", "v1")
    assert baseline != build_idempotency_key("2026-01", "hash-b", "v1")
    assert baseline != build_idempotency_key("2026-01", "hash-a", "v2")


def test_success_exposes_logical_idempotency_without_global_state(validator, command):
    runner = orchestrator(validator, FakeChampionService(champion_output()))
    first = runner.run(command)
    second = runner.run(command)
    assert first.idempotency_key == second.idempotency_key
    assert first.status == second.status == RunStatus.READY_TO_PERSIST


def test_validation_failure_stops_before_champion(validator):
    service = FakeChampionService(champion_output())
    result = orchestrator(validator, service).run(
        MonthlyRunCommand("2026-01", "monthly.txt", b"invalid", "request-invalid")
    )
    assert result.status == RunStatus.FAILED
    assert result.error_code == ErrorCode.INVALID_UPLOAD
    assert result.error_stage == RunStatus.VALIDATING
    assert service.calls == []
    assert result.snapshot is None


def test_champion_failure_stops_before_mapper(validator, command):
    mapper = SpyMapper()
    service = FakeChampionService(
        error=ContractError(
            ErrorCode.CHAMPION_NOT_READY,
            "Champion unavailable",
            stage=RunStatus.INFERENCING,
        )
    )
    result = orchestrator(validator, service, mapper).run(command)
    assert result.status == RunStatus.FAILED
    assert result.error_code == ErrorCode.CHAMPION_NOT_READY
    assert result.error_stage == RunStatus.INFERENCING
    assert mapper.calls == 0


def test_mapping_failure_is_observable_at_mapping_stage(validator, command):
    mapper = SpyMapper(
        ContractError(ErrorCode.MAPPING_FAILED, "Mapping rejected", stage=RunStatus.MAPPING)
    )
    result = orchestrator(validator, FakeChampionService(champion_output()), mapper).run(command)
    assert result.status == RunStatus.FAILED
    assert result.error_code == ErrorCode.MAPPING_FAILED
    assert result.error_stage == RunStatus.MAPPING
    assert result.snapshot is None


def test_unexpected_failure_is_sanitized(validator, command):
    result = orchestrator(
        validator,
        FakeChampionService(error=RuntimeError("secret /private/model/path")),
    ).run(command)
    assert result.error_code == ErrorCode.INTERNAL_ERROR
    assert result.error_stage == RunStatus.INFERENCING
    assert "secret" not in result.error_message
    assert "/private" not in result.error_message


def test_orchestrator_depends_only_on_hu004_service_boundary():
    source = inspect.getsource(sys.modules[MonthlyPredictionOrchestrator.__module__])
    forbidden = (
        "ChampionInput", "MaterializedChampionResult", "MaterializedOutputAdapter",
        "MaterializedChampionProvider", "ExecutableChampionProvider", "ProviderStrategy",
    )
    assert all(name not in source for name in forbidden)
    assert "ChampionService" in source
    assert "ChampionOperationalContext" in source


def test_hu005_import_has_no_ml_cloud_dataframe_or_storage_dependency():
    script = """
import json
import sys
import api.app.orchestration.monthly
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy', 'sqlite3')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []


def test_run_status_keeps_completed_reserved_for_hu006():
    assert RunStatus.MAPPING == "MAPPING"
    assert RunStatus.READY_TO_PERSIST == "READY_TO_PERSIST"
    assert RunStatus.COMPLETED not in (
        RunStatus.RECEIVED,
        RunStatus.VALIDATING,
        RunStatus.PREPARING,
        RunStatus.INFERENCING,
        RunStatus.MAPPING,
        RunStatus.READY_TO_PERSIST,
    )
