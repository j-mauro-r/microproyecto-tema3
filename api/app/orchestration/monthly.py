"""HU005 monthly run flow. Successful results stop before durable persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from api.app.champion.models import ChampionMetadata, ChampionOutput
from api.app.champion.service import (
    ChampionOperationalContext,
    ChampionService,
)
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadValidator, ValidatedMonthlyUpload
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


@dataclass(frozen=True, slots=True)
class MonthlyRunCommand:
    reference_month: str
    source_file_name: str
    source_bytes: bytes
    request_id: str | None = None
    content_type: str | None = "text/csv"


@dataclass(frozen=True, slots=True)
class CandidatePrediction:
    divipola: str
    municipality: str
    horizon: str
    target_month: str
    output_type: str
    probability: float | None
    expected_cases: float | None
    risk_score: float | None
    label: str | None
    decision_threshold: float | None


@dataclass(frozen=True, slots=True)
class PredictionSnapshotCandidate:
    run_id: str
    generated_at: datetime
    reference_month: str
    source_file_sha256: str
    champion: ChampionMetadata
    predictions: tuple[CandidatePrediction, ...]


@dataclass(frozen=True, slots=True)
class MonthlyRunResult:
    run_id: str
    request_id: str | None
    status: RunStatus
    stages: tuple[RunStatus, ...]
    reference_month: str
    source_file_sha256: str | None
    idempotency_key: str | None
    champion_version: str | None
    created_at: datetime
    finished_at: datetime
    snapshot: PredictionSnapshotCandidate | None
    error_code: ErrorCode | None
    error_stage: RunStatus | None
    error_message: str | None


class ResultMapper:
    """Map only evidence present in HU002 and HU004 contracts."""

    def map(
        self,
        *,
        run_id: str,
        generated_at: datetime,
        validated_upload: ValidatedMonthlyUpload,
        champion_output: ChampionOutput,
    ) -> PredictionSnapshotCandidate:
        if champion_output.reference_month != validated_upload.reference_month:
            self._invalid("reference_month_mismatch")
        if champion_output.source_file_sha256 != validated_upload.metadata.sha256:
            self._invalid("source_file_sha256_mismatch")
        predictions = tuple(
            CandidatePrediction(
                divipola=item.divipola,
                municipality=item.municipality,
                horizon=item.horizon,
                target_month=item.target_month,
                output_type=item.output_type,
                probability=item.probability,
                expected_cases=item.expected_cases,
                risk_score=item.risk_score,
                label=item.label,
                decision_threshold=item.decision_threshold,
            )
            for item in champion_output.predictions
        )
        if not predictions:
            self._invalid("predictions_empty")
        return PredictionSnapshotCandidate(
            run_id=run_id,
            generated_at=generated_at,
            reference_month=champion_output.reference_month,
            source_file_sha256=validated_upload.metadata.sha256,
            champion=champion_output.metadata,
            predictions=predictions,
        )

    @staticmethod
    def _invalid(reason: str) -> None:
        raise ContractError(
            ErrorCode.MAPPING_FAILED,
            "La salida del Champion no puede mapearse al contrato BIOMAC.",
            stage=RunStatus.MAPPING,
            details={"reason": reason},
        )


def build_idempotency_key(
    reference_month: str,
    source_file_sha256: str,
    champion_version: str,
) -> str:
    """Return a deterministic logical key; durable uniqueness belongs to HU006."""

    canonical = "\0".join((reference_month, source_file_sha256, champion_version))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MonthlyPredictionOrchestrator:
    def __init__(
        self,
        *,
        validator: MonthlyUploadValidator,
        champion_service: ChampionService,
        result_mapper: ResultMapper | None = None,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._validator = validator
        self._champion_service = champion_service
        self._result_mapper = result_mapper or ResultMapper()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._run_id_factory = run_id_factory or _new_run_id

    def run(self, command: MonthlyRunCommand) -> MonthlyRunResult:
        run_id = self._run_id_factory(command.reference_month)
        created_at = self._clock()
        stages: list[RunStatus] = [RunStatus.RECEIVED]
        current_stage = RunStatus.VALIDATING
        source_hash: str | None = None
        champion_version: str | None = None

        try:
            stages.append(current_stage)
            upload = self._validator.validate(
                filename=command.source_file_name,
                content=command.source_bytes,
                reference_month=command.reference_month,
                content_type=command.content_type,
            )
            source_hash = upload.metadata.sha256

            current_stage = RunStatus.PREPARING
            stages.append(current_stage)
            context = ChampionOperationalContext(
                reference_month=upload.reference_month,
                source_file_sha256=source_hash,
                validated_upload=upload,
            )

            current_stage = RunStatus.INFERENCING
            stages.append(current_stage)
            champion_output = self._champion_service.produce(context)
            champion_version = champion_output.metadata.version

            current_stage = RunStatus.MAPPING
            stages.append(current_stage)
            generated_at = self._clock()
            snapshot = self._result_mapper.map(
                run_id=run_id,
                generated_at=generated_at,
                validated_upload=upload,
                champion_output=champion_output,
            )
            idempotency_key = build_idempotency_key(
                upload.reference_month,
                source_hash,
                champion_version,
            )
            stages.append(RunStatus.READY_TO_PERSIST)
            return MonthlyRunResult(
                run_id=run_id,
                request_id=command.request_id,
                status=RunStatus.READY_TO_PERSIST,
                stages=tuple(stages),
                reference_month=command.reference_month,
                source_file_sha256=source_hash,
                idempotency_key=idempotency_key,
                champion_version=champion_version,
                created_at=created_at,
                finished_at=self._clock(),
                snapshot=snapshot,
                error_code=None,
                error_stage=None,
                error_message=None,
            )
        except ContractError as exc:
            return self._failed(
                command, run_id, created_at, stages, current_stage,
                source_hash, champion_version, exc.code, exc.message,
            )
        except Exception:
            return self._failed(
                command, run_id, created_at, stages, current_stage,
                source_hash, champion_version, ErrorCode.INTERNAL_ERROR,
                "Ocurrió un error interno durante el run mensual.",
            )

    def _failed(
        self,
        command: MonthlyRunCommand,
        run_id: str,
        created_at: datetime,
        stages: list[RunStatus],
        error_stage: RunStatus,
        source_hash: str | None,
        champion_version: str | None,
        error_code: ErrorCode,
        error_message: str,
    ) -> MonthlyRunResult:
        stages.append(RunStatus.FAILED)
        return MonthlyRunResult(
            run_id=run_id,
            request_id=command.request_id,
            status=RunStatus.FAILED,
            stages=tuple(stages),
            reference_month=command.reference_month,
            source_file_sha256=source_hash,
            idempotency_key=None,
            champion_version=champion_version,
            created_at=created_at,
            finished_at=self._clock(),
            snapshot=None,
            error_code=error_code,
            error_stage=error_stage,
            error_message=error_message,
        )


def _new_run_id(reference_month: str) -> str:
    return f"biomac-{reference_month}-{uuid4().hex[:12]}"
