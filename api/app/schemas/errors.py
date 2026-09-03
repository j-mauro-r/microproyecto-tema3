"""Stable public error contracts."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from api.app.schemas.base import StrictModel
from api.app.schemas.runs import RunStatus


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_UPLOAD = "INVALID_UPLOAD"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    PREDICTION_NOT_FOUND = "PREDICTION_NOT_FOUND"
    PERIOD_CONFLICT = "PERIOD_CONFLICT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CHAMPION_INPUT_INVALID = "CHAMPION_INPUT_INVALID"
    CHAMPION_NOT_READY = "CHAMPION_NOT_READY"
    PREPARATION_FAILED = "PREPARATION_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(StrictModel):
    code: ErrorCode
    message: str
    request_id: UUID
    run_id: str | None = None
    stage: RunStatus | None = None
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
