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
    mlflow_run_id: str | None = None
    artifact_sha256: str | None = None
    decision_rule_version: str | None = None
    explanation_method: str | None = None


class DataQualityRead(StrictModel):
    status: str
    last_observed_month: str
    epidemiological_completeness: float | None = None
    climate_completeness: float | None = None
    warnings: list[str]


class CurrentStatusRead(StrictModel):
    reference_month: str
    observed_cases: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    ratio_to_p75: float | None = None
    endemic_zone: str | None = None


class DecisionRuleRead(StrictModel):
    type: str | None = None
    probability_threshold: float | None = None
    target_month_p75: float | None = None
    decision_threshold_cases: float | None = None
    version: str | None = None


class ExplanationFeatureRead(StrictModel):
    feature: str
    value: float | str | None = None
    contribution: float
    group: str | None = None


class ExplanationRead(StrictModel):
    available: bool
    method: str | None = None
    scope: str | None = None
    top_features: list[ExplanationFeatureRead]


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
    decision_rule: DecisionRuleRead | None = None
    explanation: ExplanationRead = ExplanationRead(available=False, top_features=[])


class PredictionSnapshotRead(StrictModel):
    run_id: str
    generated_at: datetime
    reference_month: str
    source_file_sha256: str
    champion: ChampionRead
    predictions: list[PredictionRead]
    data_quality: DataQualityRead | None = None
    current_status: dict[str, CurrentStatusRead] = Field(default_factory=dict)


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
