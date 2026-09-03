"""Single ChampionOutput provider boundary consumed by HU005 and later layers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from api.app.champion.materialized import (
    MaterializedChampionResult,
    MaterializedOutputAdapter,
)
from api.app.champion.models import ChampionOutput
from api.app.champion.port import ChampionAdapter
from api.app.domain.champion_input import ChampionInput
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


@dataclass(frozen=True, slots=True)
class ChampionExecutionContext:
    """Neutral invocation envelope assembled at the composition boundary."""

    reference_month: str
    source_file_sha256: str | None = None
    champion_input: ChampionInput | None = None
    materialized_result: MaterializedChampionResult | Mapping[str, object] | None = None


@runtime_checkable
class ChampionOutputProvider(Protocol):
    """Only Champion operation HU005 needs to know."""

    def produce(self, context: ChampionExecutionContext) -> ChampionOutput: ...


class ExecutableChampionProvider:
    def __init__(self, adapter: ChampionAdapter) -> None:
        self._adapter = adapter

    def produce(self, context: ChampionExecutionContext) -> ChampionOutput:
        if context.champion_input is None or context.materialized_result is not None:
            _invalid_context("executable_context_invalid")
        if context.reference_month != context.champion_input.reference_month:
            _invalid_context("reference_month_mismatch")
        if (
            context.source_file_sha256 is not None
            and context.source_file_sha256 != context.champion_input.source_file_sha256
        ):
            _invalid_context("source_file_sha256_mismatch")
        return self._adapter.predict(context.champion_input)


class MaterializedChampionProvider:
    def __init__(self, adapter: MaterializedOutputAdapter | None = None) -> None:
        self._adapter = adapter or MaterializedOutputAdapter()

    def produce(self, context: ChampionExecutionContext) -> ChampionOutput:
        if context.materialized_result is None or context.champion_input is not None:
            _invalid_context("materialized_context_invalid")
        output = self._adapter.from_result(
            context.materialized_result,
            source_file_sha256=context.source_file_sha256,
        )
        if context.reference_month != output.reference_month:
            _invalid_context("reference_month_mismatch")
        return output


class ChampionProviderStrategy(StrEnum):
    MATERIALIZED = "materialized"
    EXECUTABLE = "executable"


def build_champion_output_provider(
    strategy: ChampionProviderStrategy | str,
    *,
    executable_adapter: ChampionAdapter | None = None,
    materialized_adapter: MaterializedOutputAdapter | None = None,
) -> ChampionOutputProvider:
    """Select exactly one provider; failures never trigger another strategy."""

    try:
        selected = ChampionProviderStrategy(strategy)
    except ValueError as exc:
        raise ValueError(f"unsupported Champion provider strategy: {strategy}") from exc
    if selected is ChampionProviderStrategy.MATERIALIZED:
        if executable_adapter is not None:
            raise ValueError("executable_adapter is invalid for materialized strategy")
        return MaterializedChampionProvider(materialized_adapter)
    if executable_adapter is None:
        raise ValueError("executable strategy requires executable_adapter")
    if materialized_adapter is not None:
        raise ValueError("materialized_adapter is invalid for executable strategy")
    return ExecutableChampionProvider(executable_adapter)


def _invalid_context(reason: str) -> None:
    raise ContractError(
        ErrorCode.CHAMPION_INPUT_INVALID,
        "El contexto no corresponde al provider Champion configurado.",
        stage=RunStatus.PREPARING,
        details={"reason": reason},
    )
