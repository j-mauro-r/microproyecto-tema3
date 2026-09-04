"""HU004 facade that hides provider-specific inputs from HU005 and later layers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Protocol, runtime_checkable

from api.app.champion.materialized import MaterializedChampionResult
from api.app.champion.feature_contract import require_compatible_feature_contract
from api.app.champion.models import ChampionOutput
from api.app.champion.provider import (
    ChampionExecutionContext,
    ChampionOutputProvider,
    ChampionProviderStrategy,
    ExecutableChampionProvider,
    MaterializedChampionProvider,
)
from api.app.domain.champion_input import ChampionInput, ChampionInputBuilder
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
)
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import ValidatedMonthlyUpload
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


@dataclass(frozen=True, slots=True)
class ChampionOperationalContext:
    """Provider-neutral information available to the monthly workflow."""

    reference_month: str
    source_file_sha256: str | None = None
    validated_upload: ValidatedMonthlyUpload | None = None


@runtime_checkable
class ChampionService(Protocol):
    """The complete HU004 boundary exposed to HU005."""

    def produce(self, context: ChampionOperationalContext) -> ChampionOutput: ...


class MaterializedChampionResultProvider(Protocol):
    def get_result(
        self, reference_month: str
    ) -> MaterializedChampionResult | Mapping[str, object]: ...


class ChampionInputProvider(Protocol):
    def get_input(self, context: ChampionOperationalContext) -> ChampionInput: ...


class CallableMaterializedChampionResultProvider:
    """Injectable bridge to a package/function/store chosen by composition."""

    def __init__(
        self,
        resolver: Callable[
            [str], MaterializedChampionResult | Mapping[str, object]
        ],
    ) -> None:
        self._resolver = resolver

    def get_result(
        self, reference_month: str
    ) -> MaterializedChampionResult | Mapping[str, object]:
        return self._resolver(reference_month)


class ValidatedUploadChampionInputProvider:
    """Delegate HU003 adaptation without moving its logic into HU004."""

    def __init__(self, builder: ChampionInputBuilder | None = None) -> None:
        self._builder = builder or ChampionInputBuilder()

    def get_input(self, context: ChampionOperationalContext) -> ChampionInput:
        if context.validated_upload is None:
            _invalid_operational_context("validated_upload_required")
        if context.reference_month != context.validated_upload.reference_month:
            _invalid_operational_context("reference_month_mismatch")
        champion_input = self._builder.build(context.validated_upload)
        if (
            context.source_file_sha256 is not None
            and context.source_file_sha256 != champion_input.source_file_sha256
        ):
            _invalid_operational_context("source_file_sha256_mismatch")
        return champion_input


class _MaterializedChampionService:
    def __init__(
        self,
        result_provider: MaterializedChampionResultProvider,
        output_provider: ChampionOutputProvider,
    ) -> None:
        self._result_provider = result_provider
        self._output_provider = output_provider

    def produce(self, context: ChampionOperationalContext) -> ChampionOutput:
        try:
            result = self._result_provider.get_result(context.reference_month)
        except ContractError:
            raise
        except Exception as exc:
            raise ContractError(
                ErrorCode.CHAMPION_NOT_READY,
                "La salida materializada del Champion no está disponible.",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                stage=RunStatus.INFERENCING,
                details={"reason": "materialized_result_unavailable"},
            ) from exc
        try:
            output = self._output_provider.produce(
                ChampionExecutionContext(
                    reference_month=context.reference_month,
                    source_file_sha256=context.source_file_sha256,
                    materialized_result=result,
                )
            )
            require_compatible_feature_contract(
                expected_version=CHAMPION_FEATURE_CONTRACT_VERSION,
                expected_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
                received=output.metadata,
            )
            return output
        except ContractError:
            raise
        except Exception as exc:
            raise ContractError(
                ErrorCode.INFERENCE_FAILED,
                "La salida materializada del Champion no cumple el contrato.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                stage=RunStatus.INFERENCING,
                details={"reason": "materialized_result_invalid"},
            ) from exc


class _ExecutableChampionService:
    def __init__(
        self,
        input_provider: ChampionInputProvider,
        output_provider: ChampionOutputProvider,
    ) -> None:
        self._input_provider = input_provider
        self._output_provider = output_provider

    def produce(self, context: ChampionOperationalContext) -> ChampionOutput:
        try:
            champion_input = self._input_provider.get_input(context)
        except ContractError:
            raise
        except Exception as exc:
            raise ContractError(
                ErrorCode.CHAMPION_INPUT_INVALID,
                "No fue posible resolver el input del Champion.",
                stage=RunStatus.PREPARING,
                details={"reason": "champion_input_resolution_failed"},
            ) from exc
        output = self._output_provider.produce(
            ChampionExecutionContext(
                reference_month=context.reference_month,
                source_file_sha256=context.source_file_sha256,
                champion_input=champion_input,
            )
        )
        require_compatible_feature_contract(
            expected_version=champion_input.feature_contract_version,
            expected_sha256=champion_input.feature_contract_sha256,
            received=output.metadata,
        )
        return output


def build_champion_service(
    strategy: ChampionProviderStrategy | str,
    *,
    materialized_result_provider: MaterializedChampionResultProvider | None = None,
    materialized_output_provider: ChampionOutputProvider | None = None,
    executable_input_provider: ChampionInputProvider | None = None,
    executable_output_provider: ChampionOutputProvider | None = None,
) -> ChampionService:
    """Compose one closed strategy. This function contains no runtime fallback."""

    try:
        selected = ChampionProviderStrategy(strategy)
    except ValueError as exc:
        raise ValueError(f"unsupported Champion service strategy: {strategy}") from exc

    if selected is ChampionProviderStrategy.MATERIALIZED:
        if materialized_result_provider is None:
            raise ValueError("materialized strategy requires a result provider")
        if executable_input_provider is not None or executable_output_provider is not None:
            raise ValueError("executable dependencies are invalid for materialized strategy")
        return _MaterializedChampionService(
            materialized_result_provider,
            materialized_output_provider or MaterializedChampionProvider(),
        )

    if executable_input_provider is None or executable_output_provider is None:
        raise ValueError("executable strategy requires input and output providers")
    if materialized_result_provider is not None or materialized_output_provider is not None:
        raise ValueError("materialized dependencies are invalid for executable strategy")
    if not isinstance(executable_output_provider, ExecutableChampionProvider):
        raise ValueError("executable output provider has the wrong strategy")
    return _ExecutableChampionService(
        executable_input_provider,
        executable_output_provider,
    )


def _invalid_operational_context(reason: str) -> None:
    raise ContractError(
        ErrorCode.CHAMPION_INPUT_INVALID,
        "El contexto operacional del Champion no es válido.",
        stage=RunStatus.PREPARING,
        details={"reason": reason},
    )
