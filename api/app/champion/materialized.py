"""Strict adapter for the materialized ChampionResult contract supplied by PR #12."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from api.app.champion.adapter import MUNICIPALITY_NAMES
from api.app.champion.models import ChampionMetadata, ChampionOutput, ChampionPrediction

_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
_EXPECTED_KEYS = frozenset(
    (divipola, horizon)
    for divipola in MUNICIPALITY_NAMES
    for horizon in ("T+1", "T+2")
)
_RESULT_FIELDS = frozenset(
    {
        "model_name",
        "model_version",
        "reference_month",
        "feature_contract_version",
        "feature_contract_sha256",
        "output_type",
        "predictions",
    }
)
_PREDICTION_FIELDS = frozenset(
    {
        "divipola",
        "municipality",
        "horizon",
        "target_month",
        "probability",
        "threshold",
        "label",
    }
)


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _probability(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"{field_name} must be finite and between zero and one")
    return result


def _month(value: object, field_name: str) -> str:
    text = _non_empty(value, field_name)
    match = _MONTH_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"{field_name} must use YYYY-MM")
    try:
        date(int(match.group(1)), int(match.group(2)), 1)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid month") from exc
    return text


def _target_month(reference_month: str, horizon: str) -> str:
    year, month = (int(part) for part in reference_month.split("-"))
    offset = 1 if horizon == "T+1" else 2
    absolute_month = year * 12 + month - 1 + offset
    target_year, target_month = divmod(absolute_month, 12)
    return f"{target_year:04d}-{target_month + 1:02d}"


@dataclass(frozen=True, slots=True)
class MaterializedChampionPrediction:
    divipola: str
    municipality: str
    horizon: str
    target_month: str
    probability: float
    threshold: float
    label: str

    def __post_init__(self) -> None:
        if self.divipola not in MUNICIPALITY_NAMES:
            raise ValueError("unsupported municipality")
        if self.municipality != MUNICIPALITY_NAMES[self.divipola]:
            raise ValueError("municipality name does not match divipola")
        if self.horizon not in {"T+1", "T+2"}:
            raise ValueError("unsupported horizon")
        _month(self.target_month, "target_month")
        _probability(self.probability, "probability")
        _probability(self.threshold, "threshold")
        expected_label = "EXCESO" if self.probability >= self.threshold else "NO_EXCESO"
        if self.label != expected_label:
            raise ValueError("label is inconsistent with probability and threshold")


@dataclass(frozen=True, slots=True)
class MaterializedChampionResult:
    model_name: str
    model_version: str
    reference_month: str
    feature_contract_version: str
    feature_contract_sha256: str
    output_type: str
    predictions: tuple[MaterializedChampionPrediction, ...]

    def __post_init__(self) -> None:
        _non_empty(self.model_name, "model_name")
        _non_empty(self.model_version, "model_version")
        _month(self.reference_month, "reference_month")
        _non_empty(self.feature_contract_version, "feature_contract_version")
        _non_empty(self.feature_contract_sha256, "feature_contract_sha256")
        if self.output_type != "probability":
            raise ValueError("PR12 output_type must be probability")
        if not isinstance(self.predictions, tuple):
            raise ValueError("predictions must be an immutable tuple")
        keys = [(item.divipola, item.horizon) for item in self.predictions]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate municipality/horizon prediction")
        if set(keys) != _EXPECTED_KEYS:
            raise ValueError("predictions must contain the exact PR12 MVP combinations")
        for item in self.predictions:
            if item.target_month != _target_month(self.reference_month, item.horizon):
                raise ValueError("target_month is inconsistent with reference_month and horizon")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> MaterializedChampionResult:
        _require_exact_fields(value, _RESULT_FIELDS, "ChampionResult")
        raw_predictions = value["predictions"]
        if not isinstance(raw_predictions, Sequence) or isinstance(raw_predictions, (str, bytes)):
            raise ValueError("predictions must be an array")
        predictions = tuple(_prediction_from_mapping(item) for item in raw_predictions)
        return cls(
            model_name=_non_empty(value["model_name"], "model_name"),
            model_version=_non_empty(value["model_version"], "model_version"),
            reference_month=_month(value["reference_month"], "reference_month"),
            feature_contract_version=_non_empty(
                value["feature_contract_version"], "feature_contract_version"
            ),
            feature_contract_sha256=_non_empty(
                value["feature_contract_sha256"], "feature_contract_sha256"
            ),
            output_type=_non_empty(value["output_type"], "output_type"),
            predictions=predictions,
        )


def _require_exact_fields(
    value: Mapping[str, object], expected: frozenset[str], contract_name: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{contract_name} fields mismatch; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _prediction_from_mapping(value: object) -> MaterializedChampionPrediction:
    if not isinstance(value, Mapping):
        raise ValueError("each prediction must be an object")
    _require_exact_fields(value, _PREDICTION_FIELDS, "prediction")
    return MaterializedChampionPrediction(
        divipola=_non_empty(value["divipola"], "divipola"),
        municipality=_non_empty(value["municipality"], "municipality"),
        horizon=_non_empty(value["horizon"], "horizon"),
        target_month=_month(value["target_month"], "target_month"),
        probability=_probability(value["probability"], "probability"),
        threshold=_probability(value["threshold"], "threshold"),
        label=_non_empty(value["label"], "label"),
    )


class MaterializedOutputAdapter:
    """Map an already-produced PR12 result; this class never executes a model."""

    def from_result(
        self,
        result: MaterializedChampionResult | Mapping[str, object],
        source_file_sha256: str | None = None,
    ) -> ChampionOutput:
        materialized = (
            result
            if isinstance(result, MaterializedChampionResult)
            else MaterializedChampionResult.from_mapping(_as_mapping(result))
        )
        if source_file_sha256 is not None:
            _non_empty(source_file_sha256, "source_file_sha256")
        metadata = ChampionMetadata(
            name=materialized.model_name,
            version=materialized.model_version,
            supported_horizons=("T+1", "T+2"),
            output_type=materialized.output_type,
            feature_contract_version=materialized.feature_contract_version,
            feature_contract_sha256=materialized.feature_contract_sha256,
        )
        by_key = {(item.divipola, item.horizon): item for item in materialized.predictions}
        predictions = tuple(
            ChampionPrediction(
                divipola=divipola,
                municipality=item.municipality,
                horizon=horizon,
                target_month=item.target_month,
                output_type=materialized.output_type,
                probability=item.probability,
                label=item.label,
                decision_threshold=item.threshold,
            )
            for divipola in MUNICIPALITY_NAMES
            for horizon in ("T+1", "T+2")
            for item in (by_key[(divipola, horizon)],)
        )
        return ChampionOutput(
            reference_month=materialized.reference_month,
            predictions=predictions,
            metadata=metadata,
            source_file_sha256=source_file_sha256,
        )


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("result must be MaterializedChampionResult or an object mapping")
    return value
