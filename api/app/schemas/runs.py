"""Operational run and Champion metadata contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from api.app.schemas.base import StrictModel


class RunStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    PREPARING = "PREPARING"
    INFERENCING = "INFERENCING"
    MAPPING = "MAPPING"
    READY_TO_PERSIST = "READY_TO_PERSIST"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Horizon(StrEnum):
    T_PLUS_1 = "T+1"
    T_PLUS_2 = "T+2"


class SourceFileMetadata(StrictModel):
    original_name: str
    sha256: str
    size_bytes: int = Field(ge=0)


class ChampionMetadata(StrictModel):
    name: str
    version: str
    mlflow_run_id: str | None = None
    artifact_id: str | None = None
    output_type: str
    supported_horizons: list[Horizon]
    feature_contract_version: str
    decision_rule_version: str | None = None
    explanation_method: str | None = None


class RunMetadata(StrictModel):
    run_id: str
    status: RunStatus
    reference_month: str
    created_at: datetime
    completed_at: datetime | None = None
    source_file: SourceFileMetadata | None = None
    source_file_sha256: str | None = None
    champion: ChampionMetadata | None = None
    champion_version: str | None = None
    stage: RunStatus | None = None
    error_code: str | None = None
    error_message: str | None = None
