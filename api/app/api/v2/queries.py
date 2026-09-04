"""Thin HTTP boundary for HU007 read-only queries."""

from http import HTTPStatus

from fastapi import APIRouter, Query, Request

from api.app.domain.errors import ContractError
from api.app.query.service import HistoryFilters, PredictionQueryService, RunQueryService
from api.app.schemas.errors import ErrorCode
from api.app.schemas.read_models import (
    PredictionHistoryResponse, PredictionSnapshotReadResponse, RunReadResponse,
)

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunReadResponse, tags=["runs"])
def get_run(request: Request, run_id: str) -> RunReadResponse:
    service: RunQueryService = request.app.state.run_query_service
    return service.get(run_id, str(request.state.request_id))


@router.get(
    "/predictions/latest", response_model=PredictionSnapshotReadResponse,
    tags=["predictions"],
)
def get_latest_prediction(
    request: Request,
    municipality_codes: list[str] | None = Query(default=None),
    horizons: list[str] | None = Query(default=None),
) -> PredictionSnapshotReadResponse:
    service: PredictionQueryService = request.app.state.prediction_query_service
    return service.latest(
        str(request.state.request_id),
        _multiple(municipality_codes),
        _multiple(horizons),
    )


@router.get(
    "/predictions/history", response_model=PredictionHistoryResponse,
    tags=["predictions"],
)
def get_prediction_history(
    request: Request,
    municipality_codes: list[str] | None = Query(default=None),
    horizon: str | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
    limit: str = "20",
    offset: str = "0",
) -> PredictionHistoryResponse:
    service: PredictionQueryService = request.app.state.prediction_query_service
    try:
        parsed_limit, parsed_offset = int(limit), int(offset)
    except ValueError as exc:
        raise ContractError(
            ErrorCode.INVALID_REQUEST, "Los filtros de consulta no son válidos.",
            status_code=HTTPStatus.BAD_REQUEST,
            details={"reason": "pagination_invalid"},
        ) from exc
    return service.history(str(request.state.request_id), HistoryFilters(
        municipality_codes=_multiple(municipality_codes), horizon=horizon,
        from_month=from_month, to_month=to_month,
        limit=parsed_limit, offset=parsed_offset,
    ))


def _multiple(values: list[str] | None) -> tuple[str, ...]:
    return tuple(
        part.strip() for value in (values or []) for part in value.split(",") if part.strip()
    )
