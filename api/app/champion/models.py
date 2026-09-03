"""Immutable domain contracts emitted by the Champion boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _required(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _optional_finite(value: float | None, field_name: str) -> None:
    if value is not None and not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class ChampionMetadata:
    name: str
    version: str
    supported_horizons: tuple[str, ...]
    output_type: str
    feature_contract_version: str
    feature_contract_sha256: str
    decision_threshold: float | None = None
    mlflow_run_id: str | None = None
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.name, "name"),
            (self.version, "version"),
            (self.output_type, "output_type"),
            (self.feature_contract_version, "feature_contract_version"),
            (self.feature_contract_sha256, "feature_contract_sha256"),
        ):
            _required(value, field_name)
        if not self.supported_horizons or any(
            horizon not in {"T+1", "T+2"} for horizon in self.supported_horizons
        ):
            raise ValueError("supported_horizons must contain only supported BIOMAC horizons")
        if len(set(self.supported_horizons)) != len(self.supported_horizons):
            raise ValueError("supported_horizons must not contain duplicates")
        _optional_finite(self.decision_threshold, "decision_threshold")
        if self.decision_threshold is not None and not 0 <= self.decision_threshold <= 1:
            raise ValueError("decision_threshold must be between zero and one")


@dataclass(frozen=True, slots=True)
class ChampionPrediction:
    divipola: str
    horizon: str
    target_month: str
    output_type: str
    probability: float | None = None
    expected_cases: float | None = None
    risk_score: float | None = None
    label: str | None = None
    decision_threshold: float | None = None

    def __post_init__(self) -> None:
        if self.divipola not in {"68001", "76001"}:
            raise ValueError("unsupported municipality")
        if self.horizon not in {"T+1", "T+2"}:
            raise ValueError("unsupported horizon")
        _required(self.target_month, "target_month")
        _required(self.output_type, "output_type")
        for value, field_name in (
            (self.probability, "probability"),
            (self.expected_cases, "expected_cases"),
            (self.risk_score, "risk_score"),
            (self.decision_threshold, "decision_threshold"),
        ):
            _optional_finite(value, field_name)
        if self.probability is not None and not 0 <= self.probability <= 1:
            raise ValueError("probability must be between zero and one")
        if self.decision_threshold is not None and not 0 <= self.decision_threshold <= 1:
            raise ValueError("decision_threshold must be between zero and one")


@dataclass(frozen=True, slots=True)
class ChampionOutput:
    reference_month: str
    predictions: tuple[ChampionPrediction, ...]
    metadata: ChampionMetadata
    source_file_sha256: str

    def __post_init__(self) -> None:
        _required(self.reference_month, "reference_month")
        _required(self.source_file_sha256, "source_file_sha256")
