"""Truthful HU009 metadata, quality, context and explanation contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from api.app.champion.models import ChampionMetadata
from api.app.domain.monthly_uploads import ValidatedMonthlyUpload


@dataclass(frozen=True, slots=True)
class DataQualitySnapshot:
    status: str
    last_observed_month: str
    epidemiological_completeness: float | None = None
    climate_completeness: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CurrentStatusSnapshot:
    reference_month: str
    observed_cases: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    ratio_to_p75: float | None = None
    endemic_zone: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionRuleSnapshot:
    type: str | None
    probability_threshold: float | None = None
    target_month_p75: float | None = None
    decision_threshold_cases: float | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class ExplanationFeature:
    feature: str
    value: float | str | None
    contribution: float
    group: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.contribution):
            raise ValueError("contribution must be finite")


@dataclass(frozen=True, slots=True)
class LocalExplanation:
    available: bool
    method: str | None = None
    scope: str | None = None
    top_features: tuple[ExplanationFeature, ...] = ()

    def __post_init__(self) -> None:
        if not self.available and (self.method or self.scope or self.top_features):
            raise ValueError("unavailable explanation cannot contain evidence")
        if self.available and (self.scope != "local" or not self.top_features):
            raise ValueError("available explanation must be local and non-empty")


class LocalExplanationProvider(Protocol):
    def get_explanation(self, *, reference_month: str, divipola: str, horizon: str,
                        champion_metadata: ChampionMetadata) -> LocalExplanation: ...


class UnavailableExplanationProvider:
    def get_explanation(self, **_: object) -> LocalExplanation:
        return LocalExplanation(available=False)


class MaterializedShapExplanationProvider:
    """Read an exact inference row from explicitly configured local parquet files."""

    def __init__(self, artifacts: dict[str, str], *,
                 feature_contract_version: str | None = None,
                 feature_contract_sha256: str | None = None,
                 top_n: int = 10) -> None:
        self._artifacts = dict(artifacts)
        self._feature_contract_version = feature_contract_version
        self._feature_contract_sha256 = feature_contract_sha256
        self._top_n = top_n

    def get_explanation(self, *, reference_month: str, divipola: str, horizon: str,
                        champion_metadata: ChampionMetadata) -> LocalExplanation:
        path = self._artifacts.get(horizon)
        if (not path or not Path(path).is_file()
                or self._feature_contract_version != champion_metadata.feature_contract_version
                or self._feature_contract_sha256 != champion_metadata.feature_contract_sha256):
            return LocalExplanation(available=False)
        try:
            import pyarrow.parquet as parquet
            year, month = (int(part) for part in reference_month.split("-"))
            table = parquet.read_table(path)
            rows = [row for row in table.to_pylist()
                    if str(row.get("divipola")) == divipola
                    and int(row.get("anio")) == year and int(row.get("mes")) == month]
            if len(rows) != 1:
                return LocalExplanation(available=False)
            row = rows[0]
            features = []
            for key, raw in row.items():
                if not key.startswith("shap_"):
                    continue
                contribution = float(raw)
                if not math.isfinite(contribution):
                    return LocalExplanation(available=False)
                feature = key.removeprefix("shap_")
                features.append(ExplanationFeature(feature, row.get(feature), contribution))
            features.sort(key=lambda item: abs(item.contribution), reverse=True)
            return LocalExplanation(True, "shap", "local", tuple(features[: self._top_n]))
        except Exception:
            return LocalExplanation(available=False)


def build_quality(upload: ValidatedMonthlyUpload) -> DataQualitySnapshot:
    return DataQualitySnapshot(
        status="complete",
        last_observed_month=upload.reference_month,
        warnings=(
            "Las 39 features requeridas fueron validadas; la completitud por grupo "
            "epidemiológico/climático no tiene denominador contractual y permanece nula.",
        ),
    )


def build_current_status(upload: ValidatedMonthlyUpload) -> dict[str, CurrentStatusSnapshot]:
    result = {}
    for row in upload.rows:
        result[row["divipola"]] = CurrentStatusSnapshot(
            reference_month=upload.reference_month,
            observed_cases=None,
            p25=float(row["p25"]),
            p50=None,
            p75=float(row["p75"]),
            ratio_to_p75=None,
            endemic_zone=row["zona_canal"],
        )
    return result


def ratio_to_p75(observed_cases: float | None, p75: float | None) -> float | None:
    return observed_cases / p75 if observed_cases is not None and p75 is not None and p75 > 0 else None
