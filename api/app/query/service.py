"""Framework-neutral queries over the HU006 durable store."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import re
from typing import Protocol

from api.app.domain.errors import ContractError
from api.app.orchestration.monthly import MonthlyRunResult, PredictionSnapshotCandidate
from api.app.schemas.errors import ErrorCode
from api.app.schemas.read_models import (
    ChampionRead, PaginationMeta, PredictionHistoryItem, PredictionHistoryResponse,
    PredictionRead, PredictionSnapshotRead, PredictionSnapshotReadResponse,
    RunErrorRead, RunRead, RunReadResponse,
)
from api.app.schemas.runs import RunStatus

SUPPORTED_MUNICIPALITIES = frozenset({"68001", "76001"})
SUPPORTED_HORIZONS = frozenset({"T+1", "T+2"})
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PredictionQueryRepository(Protocol):
    def get_run(self, run_id: str) -> MonthlyRunResult | None: ...
    def get_latest_completed(
        self, municipality_codes: tuple[str, ...], horizons: tuple[str, ...]
    ) -> MonthlyRunResult | None: ...
    def list_completed(
        self, filters: HistoryFilters
    ) -> tuple[MonthlyRunResult, ...]: ...


@dataclass(frozen=True, slots=True)
class HistoryFilters:
    municipality_codes: tuple[str, ...]
    horizon: str | None
    from_month: str | None
    to_month: str | None
    limit: int
    offset: int


class RunQueryService:
    def __init__(self, repository: PredictionQueryRepository) -> None:
        self._repository = repository

    def get(self, run_id: str, request_id: str) -> RunReadResponse:
        try:
            result = self._repository.get_run(run_id)
        except Exception as exc:
            raise _storage_failure() from exc
        if result is None:
            raise ContractError(
                ErrorCode.RUN_NOT_FOUND, "El run solicitado no existe.",
                status_code=HTTPStatus.NOT_FOUND,
                details={"run_id": run_id},
            )
        error = None
        if result.status is RunStatus.FAILED and result.error_code and result.error_stage:
            error = RunErrorRead(
                code=result.error_code, stage=result.error_stage,
                message=result.error_message or "El run mensual falló.",
            )
        return RunReadResponse(request_id=request_id, run=RunRead(
            run_id=result.run_id, status=result.status, reference_month=result.reference_month,
            stages=list(result.stages), created_at=result.created_at,
            finished_at=result.finished_at, completed_at=result.completed_at,
            source_file_sha256=result.source_file_sha256,
            champion_version=result.champion_version, error=error,
        ))


class PredictionQueryService:
    def __init__(self, repository: PredictionQueryRepository) -> None:
        self._repository = repository

    def latest(
        self, request_id: str, municipality_codes: tuple[str, ...], horizons: tuple[str, ...]
    ) -> PredictionSnapshotReadResponse:
        municipalities = _municipalities(municipality_codes)
        selected_horizons = _horizons(horizons)
        try:
            result = self._repository.get_latest_completed(municipalities, selected_horizons)
        except Exception as exc:
            raise _storage_failure() from exc
        if result is None or result.snapshot is None:
            raise ContractError(
                ErrorCode.PREDICTION_NOT_FOUND,
                "No existe una predicción completada para los filtros solicitados.",
                status_code=HTTPStatus.NOT_FOUND,
            )
        snapshot = _snapshot(result.snapshot, municipalities, selected_horizons)
        if not snapshot.predictions:
            raise ContractError(
                ErrorCode.PREDICTION_NOT_FOUND,
                "No existe una predicción completada para los filtros solicitados.",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return PredictionSnapshotReadResponse(
            request_id=request_id, prediction_snapshot=snapshot
        )

    def history(
        self, request_id: str, filters: HistoryFilters
    ) -> PredictionHistoryResponse:
        validated = _history_filters(filters)
        try:
            results = self._repository.list_completed(validated)
        except Exception as exc:
            raise _storage_failure() from exc
        horizons = (validated.horizon,) if validated.horizon else tuple(sorted(SUPPORTED_HORIZONS))
        items = []
        for result in results:
            if result.snapshot is None or result.completed_at is None:
                continue
            snapshot = _snapshot(result.snapshot, validated.municipality_codes, horizons)
            items.append(PredictionHistoryItem(
                **snapshot.model_dump(), completed_at=result.completed_at
            ))
        return PredictionHistoryResponse(
            request_id=request_id, items=items,
            pagination=PaginationMeta(
                limit=validated.limit, offset=validated.offset, returned=len(items)
            ),
        )


def _snapshot(
    snapshot: PredictionSnapshotCandidate,
    municipality_codes: tuple[str, ...], horizons: tuple[str, ...],
) -> PredictionSnapshotRead:
    champion = snapshot.champion
    return PredictionSnapshotRead(
        run_id=snapshot.run_id, generated_at=snapshot.generated_at,
        reference_month=snapshot.reference_month,
        source_file_sha256=snapshot.source_file_sha256,
        champion=ChampionRead(
            name=champion.name, version=champion.version, output_type=champion.output_type,
            supported_horizons=list(champion.supported_horizons),
            feature_contract_version=champion.feature_contract_version,
            feature_contract_sha256=champion.feature_contract_sha256,
        ),
        predictions=[PredictionRead(**{
            field: getattr(item, field) for field in PredictionRead.model_fields
        }) for item in snapshot.predictions
            if item.divipola in municipality_codes and item.horizon in horizons],
    )


def _municipalities(values: tuple[str, ...]) -> tuple[str, ...]:
    selected = values or tuple(sorted(SUPPORTED_MUNICIPALITIES))
    if not selected or any(value not in SUPPORTED_MUNICIPALITIES for value in selected):
        _invalid("municipality_codes_invalid")
    return tuple(dict.fromkeys(selected))


def _horizons(values: tuple[str, ...]) -> tuple[str, ...]:
    selected = values or ("T+1", "T+2")
    if any(value not in SUPPORTED_HORIZONS for value in selected):
        _invalid("horizons_invalid")
    return tuple(dict.fromkeys(selected))


def _history_filters(filters: HistoryFilters) -> HistoryFilters:
    municipalities = _municipalities(filters.municipality_codes)
    if filters.horizon is not None and filters.horizon not in SUPPORTED_HORIZONS:
        _invalid("horizon_invalid")
    for value, reason in ((filters.from_month, "from_month_invalid"),
                          (filters.to_month, "to_month_invalid")):
        if value is not None and _MONTH.fullmatch(value) is None:
            _invalid(reason)
    if filters.from_month and filters.to_month and filters.from_month > filters.to_month:
        _invalid("month_range_invalid")
    if not 1 <= filters.limit <= 100:
        _invalid("limit_invalid")
    if filters.offset < 0:
        _invalid("offset_invalid")
    return HistoryFilters(municipalities, filters.horizon, filters.from_month,
                          filters.to_month, filters.limit, filters.offset)


def _invalid(reason: str) -> None:
    raise ContractError(
        ErrorCode.INVALID_REQUEST, "Los filtros de consulta no son válidos.",
        status_code=HTTPStatus.BAD_REQUEST, details={"reason": reason},
    )


def _storage_failure() -> ContractError:
    return ContractError(
        ErrorCode.PERSISTENCE_FAILED, "No fue posible consultar los datos persistidos.",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        details={"reason": "read_storage_unavailable"},
    )
