"""Strict, minimal contracts backed by HU006 persistence."""

from datetime import datetime

from pydantic import Field

from api.app.schemas.base import StrictModel
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


class RunErrorRead(StrictModel):
    code: ErrorCode
    stage: RunStatus
    message: str


class RunRead(StrictModel):
    run_id: str
    status: RunStatus
    reference_month: str
    stages: list[RunStatus]
    created_at: datetime
    finished_at: datetime
    completed_at: datetime | None
    source_file_sha256: str | None
    champion_version: str | None
    error: RunErrorRead | None


class RunReadResponse(StrictModel):
    schema_version: str = "2.0.0"
    request_id: str
    run: RunRead


class ChampionRead(StrictModel):
    name: str
    version: str
    output_type: str
    supported_horizons: list[str]
    feature_contract_version: str
    feature_contract_sha256: str


class PredictionRead(StrictModel):
    divipola: str = Field(pattern=r"^\d{5}$")
    municipality: str
    horizon: str
    target_month: str
    output_type: str
    probability: float | None
    expected_cases: float | None
    risk_score: float | None
    label: str | None
    decision_threshold: float | None


class PredictionSnapshotRead(StrictModel):
    run_id: str
    generated_at: datetime
    reference_month: str
    source_file_sha256: str
    champion: ChampionRead
    predictions: list[PredictionRead]


class PredictionSnapshotReadResponse(StrictModel):
    schema_version: str = "2.0.0"
    request_id: str
    prediction_snapshot: PredictionSnapshotRead


class PredictionHistoryItem(PredictionSnapshotRead):
    completed_at: datetime


class PaginationMeta(StrictModel):
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    returned: int = Field(ge=0)


class PredictionHistoryResponse(StrictModel):
    schema_version: str = "2.0.0"
    request_id: str
    items: list[PredictionHistoryItem]
    pagination: PaginationMeta
