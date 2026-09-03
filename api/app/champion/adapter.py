"""Lazy, framework-neutral adapter and production loading boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
from threading import Lock
from typing import Protocol

from api.app.champion.models import ChampionMetadata, ChampionOutput, ChampionPrediction
from api.app.domain.champion_feature_contract import CHAMPION_FEATURES
from api.app.domain.champion_input import ChampionInput, MUNICIPALITY_ORDER
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus

MUNICIPALITY_NAMES: dict[str, str] = {
    "68001": "Bucaramanga",
    "76001": "Cali",
}


@dataclass(frozen=True, slots=True)
class NativePrediction:
    """Framework-free record returned by an installed Champion runtime."""

    divipola: str
    horizon: str
    probability: float | None = None
    expected_cases: float | None = None
    risk_score: float | None = None
    label: str | None = None


class ChampionRuntime(Protocol):
    metadata: ChampionMetadata

    def predict(self, inference_input: ChampionInput) -> tuple[NativePrediction, ...]: ...


class ChampionLoader(Protocol):
    def load(self) -> ChampionRuntime: ...


class MissingChampionLoader:
    """Truthful production default until modelling supplies an approved package."""

    def load(self) -> ChampionRuntime:
        raise RuntimeError("approved Champion package is not configured")


class LazyChampionAdapter:
    """Load a configured runtime once and enforce the HU004 boundary."""

    def __init__(self, loader: ChampionLoader) -> None:
        self._loader = loader
        self._runtime: ChampionRuntime | None = None
        self._load_lock = Lock()

    def metadata(self) -> ChampionMetadata:
        return self._load().metadata

    def predict(self, inference_input: ChampionInput) -> ChampionOutput:
        runtime = self._load()
        metadata = runtime.metadata
        self._validate_input(inference_input, metadata)
        try:
            native_predictions = runtime.predict(inference_input)
            predictions = self._map_predictions(
                native_predictions, inference_input.reference_month, metadata
            )
        except ContractError:
            raise
        except Exception as exc:
            raise ContractError(
                ErrorCode.INFERENCE_FAILED,
                "La inferencia del Champion no pudo completarse.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                stage=RunStatus.INFERENCING,
                details={"reason": "champion_execution_failed"},
            ) from exc
        return ChampionOutput(
            reference_month=inference_input.reference_month,
            predictions=predictions,
            metadata=metadata,
            source_file_sha256=inference_input.source_file_sha256,
        )

    def _load(self) -> ChampionRuntime:
        if self._runtime is not None:
            return self._runtime
        with self._load_lock:
            if self._runtime is not None:
                return self._runtime
            try:
                runtime = self._loader.load()
                metadata = runtime.metadata
                if not isinstance(metadata, ChampionMetadata):
                    raise TypeError("invalid Champion metadata")
            except Exception as exc:
                raise ContractError(
                    ErrorCode.CHAMPION_NOT_READY,
                    "El Champion aprobado no está disponible.",
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    stage=RunStatus.INFERENCING,
                    details={"reason": "champion_load_failed"},
                ) from exc
            self._runtime = runtime
            return runtime

    @staticmethod
    def _validate_input(
        inference_input: ChampionInput, metadata: ChampionMetadata
    ) -> None:
        if inference_input.feature_contract_version != metadata.feature_contract_version:
            LazyChampionAdapter._invalid_input("feature_contract_version_mismatch")
        if inference_input.feature_contract_sha256 != metadata.feature_contract_sha256:
            LazyChampionAdapter._invalid_input("feature_contract_sha256_mismatch")
        if inference_input.municipalities != MUNICIPALITY_ORDER:
            LazyChampionAdapter._invalid_input("municipality_contract_violation")
        if inference_input.feature_names != CHAMPION_FEATURES:
            LazyChampionAdapter._invalid_input("feature_names_mismatch")
        if len(inference_input.rows) != len(MUNICIPALITY_ORDER) or any(
            len(row) != len(CHAMPION_FEATURES) for row in inference_input.rows
        ):
            LazyChampionAdapter._invalid_input("input_shape_violation")

    @staticmethod
    def _invalid_input(reason: str) -> None:
        raise ContractError(
            ErrorCode.CHAMPION_INPUT_INVALID,
            "El input no es compatible con el contrato del Champion.",
            stage=RunStatus.PREPARING,
            details={"reason": reason},
        )

    @staticmethod
    def _map_predictions(
        native_predictions: tuple[NativePrediction, ...],
        reference_month: str,
        metadata: ChampionMetadata,
    ) -> tuple[ChampionPrediction, ...]:
        expected_keys = {
            (divipola, horizon)
            for divipola in MUNICIPALITY_ORDER
            for horizon in metadata.supported_horizons
        }
        observed_keys = {(item.divipola, item.horizon) for item in native_predictions}
        if observed_keys != expected_keys or len(observed_keys) != len(native_predictions):
            raise ValueError("runtime output does not match municipality/horizon contract")

        by_key = {(item.divipola, item.horizon): item for item in native_predictions}
        predictions: list[ChampionPrediction] = []
        for divipola in MUNICIPALITY_ORDER:
            for horizon in metadata.supported_horizons:
                item = by_key[(divipola, horizon)]
                _validate_output_fields(item, metadata.output_type)
                threshold = metadata.decision_threshold
                label = item.label
                if label is None and threshold is not None and item.probability is not None:
                    label = "EXCESO" if item.probability >= threshold else "NO_EXCESO"
                predictions.append(
                    ChampionPrediction(
                        divipola=divipola,
                        horizon=horizon,
                        target_month=_target_month(reference_month, horizon),
                        output_type=metadata.output_type,
                        probability=item.probability,
                        expected_cases=item.expected_cases,
                        risk_score=item.risk_score,
                        label=label,
                        decision_threshold=threshold,
                    )
                )
        return tuple(predictions)


def _validate_output_fields(item: NativePrediction, output_type: str) -> None:
    output_fields = {
        "probability": item.probability,
        "expected_cases": item.expected_cases,
        "risk_score": item.risk_score,
    }
    populated = {name for name, value in output_fields.items() if value is not None}
    allowed = {output_type} if output_type in output_fields else set()
    if not populated.issubset(allowed):
        raise ValueError("runtime populated fields outside its declared output type")


def _target_month(reference_month: str, horizon: str) -> str:
    year_text, month_text = reference_month.split("-", maxsplit=1)
    offset = 1 if horizon == "T+1" else 2
    month_index = int(year_text) * 12 + int(month_text) - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1).strftime("%Y-%m")


def build_champion_adapter(loader: ChampionLoader | None = None) -> LazyChampionAdapter:
    """Composition root used now and by HU005; no model is fabricated by default."""

    return LazyChampionAdapter(loader or MissingChampionLoader())
