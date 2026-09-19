"""BIOMAC prediction snapshot contracts; no inference logic lives here."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from api.app.schemas.base import StrictModel
from api.app.schemas.runs import ChampionMetadata, Horizon


class DataQualityStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DEGRADED = "degraded"


class PredictionLabel(StrEnum):
    EXCESO = "EXCESO"
    NO_EXCESO = "NO_EXCESO"


class TargetDefinition(StrictModel):
    business_target: str
    target_series: str
    predictor_series: list[str]
    series_are_summed: bool
    excess_rule: str


class Municipality(StrictModel):
    divipola: str
    name: str
    department: str | None = None


class DataQuality(StrictModel):
    status: DataQualityStatus
    last_observed_month: str
    epidemiological_completeness: float | None = Field(default=None, ge=0, le=1)
    climate_completeness: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str]


class CurrentStatus(StrictModel):
    reference_month: str
    observed_cases: float
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    ratio_to_p75: float | None = None
    endemic_zone: str | None = None


class ModelOutput(StrictModel):
    type: str
    probability: float | None = Field(default=None, ge=0, le=1)
    expected_cases: float | None = None
    risk_score: float | None = None


class DecisionRule(StrictModel):
    type: str
    probability_threshold: float | None = Field(default=None, ge=0, le=1)
    target_month_p75: float | None = None
    multiplier_k: float | None = None
    decision_threshold_cases: float | None = None
    version: str | None = None


class TopFeature(StrictModel):
    feature: str
    value: float | str | None = None
    contribution: float | None = None
    group: str | None = None


class Explanation(StrictModel):
    available: bool
    method: str | None = None
    scope: str | None = None
    top_features: list[TopFeature]


class HorizonPrediction(StrictModel):
    horizon: Horizon
    target_month: str
    label: PredictionLabel | None = None
    model_output: ModelOutput
    decision_rule: DecisionRule
    uncertainty: dict[str, object] | None = None
    explanation: Explanation


class HistoricalObservation(StrictModel):
    month: str
    observed_cases: float
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    is_excess: bool | None = None


class MunicipalityForecast(StrictModel):
    municipality: Municipality
    data_quality: DataQuality
    current_status: CurrentStatus
    predictions: list[HorizonPrediction]
    history: list[HistoricalObservation]


class PredictionSnapshot(StrictModel):
    schema_version: str
    run_id: str
    generated_at: datetime
    reference_month: str
    source_file_sha256: str
    target_definition: TargetDefinition
    champion: ChampionMetadata
    forecasts: list[MunicipalityForecast]
    data_quality: DataQuality | None = None
