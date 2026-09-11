import json
import subprocess
import sys

import pytest

from api.app.champion.adapter import LazyChampionAdapter, NativePrediction
from api.app.champion.models import ChampionMetadata, ChampionOutput
from api.app.champion.provider import (
    ChampionExecutionContext,
    ChampionOutputProvider,
    ChampionProviderStrategy,
    ExecutableChampionProvider,
    MaterializedChampionProvider,
    build_champion_output_provider,
)
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
)
from api.app.domain.champion_input import ChampionInput
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode


@pytest.fixture
def champion_input():
    return ChampionInput(
        reference_month="2025-12",
        municipalities=("68001", "76001"),
        feature_names=CHAMPION_FEATURES,
        rows=(tuple([1.0] * 39), tuple([2.0] * 39)),
        feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
        feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
        source_file_sha256="source-sha",
    )


@pytest.fixture
def materialized_result():
    return {
        "model_name": "biomac-champion",
        "model_version": "pr12-provider-test",
        "reference_month": "2025-12",
        "feature_contract_version": "pr12-contract",
        "feature_contract_sha256": "pr12-feature-sha",
        "output_type": "probability",
        "predictions": [
            {
                "divipola": divipola,
                "municipality": municipality,
                "horizon": horizon,
                "target_month": "2026-01" if horizon == "T+1" else "2026-02",
                "probability": probability,
                "threshold": 0.61 if horizon == "T+1" else 0.67,
                "label": "EXCESO" if probability >= (0.61 if horizon == "T+1" else 0.67) else "NO_EXCESO",
            }
            for divipola, municipality, probability in (
                ("68001", "Bucaramanga", 0.72),
                ("76001", "Cali", 0.42),
            )
            for horizon in ("T+1", "T+2")
        ],
    }


class CountingRuntime:
    metadata = ChampionMetadata(
        name="executable-test",
        version="1.0.0",
        supported_horizons=("T+1",),
        output_type="probability",
        feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
        feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
    )

    def predict(self, inference_input):
        return tuple(
            NativePrediction(
                divipola=divipola,
                horizon="T+1",
                probability=0.7,
                decision_threshold=0.63,
            )
            for divipola in inference_input.municipalities
        )


class CountingLoader:
    def __init__(self):
        self.calls = 0

    def load(self):
        self.calls += 1
        return CountingRuntime()


def executable_provider():
    loader = CountingLoader()
    return ExecutableChampionProvider(LazyChampionAdapter(loader)), loader


def consume_like_hu005(provider: ChampionOutputProvider, context: ChampionExecutionContext):
    """A provider-agnostic stand-in; real HU005 is intentionally not implemented here."""

    return provider.produce(context)


def test_both_providers_satisfy_the_same_runtime_protocol():
    executable, _ = executable_provider()
    materialized = MaterializedChampionProvider()
    assert isinstance(executable, ChampionOutputProvider)
    assert isinstance(materialized, ChampionOutputProvider)


def test_same_hu005_style_consumer_accepts_either_provider(
    champion_input, materialized_result
):
    executable, _ = executable_provider()
    cases = (
        (
            executable,
            ChampionExecutionContext(
                reference_month="2025-12",
                source_file_sha256="source-sha",
                champion_input=champion_input,
            ),
        ),
        (
            MaterializedChampionProvider(),
            ChampionExecutionContext(
                reference_month="2025-12",
                source_file_sha256="source-sha",
                materialized_result=materialized_result,
            ),
        ),
    )
    outputs = [consume_like_hu005(provider, context) for provider, context in cases]
    assert all(type(output) is ChampionOutput for output in outputs)


def test_executable_provider_delegates_and_preserves_t1_only(champion_input):
    provider, _ = executable_provider()
    output = provider.produce(
        ChampionExecutionContext(
            reference_month="2025-12", champion_input=champion_input
        )
    )
    assert [(item.divipola, item.horizon) for item in output.predictions] == [
        ("68001", "T+1"), ("76001", "T+1")
    ]
    assert all(item.decision_threshold == 0.63 for item in output.predictions)


def test_executable_provider_preserves_adapter_load_once(champion_input):
    provider, loader = executable_provider()
    context = ChampionExecutionContext(
        reference_month="2025-12", champion_input=champion_input
    )
    provider.produce(context)
    provider.produce(context)
    assert loader.calls == 1


def test_materialized_provider_preserves_per_horizon_thresholds(materialized_result):
    output = MaterializedChampionProvider().produce(
        ChampionExecutionContext(
            reference_month="2025-12", materialized_result=materialized_result
        )
    )
    assert [item.decision_threshold for item in output.predictions] == [
        0.61, 0.67, 0.61, 0.67
    ]


@pytest.mark.parametrize(
    ("provider", "context", "reason"),
    [
        (
            ExecutableChampionProvider(LazyChampionAdapter(CountingLoader())),
            ChampionExecutionContext(reference_month="2025-12"),
            "executable_context_invalid",
        ),
        (
            MaterializedChampionProvider(),
            ChampionExecutionContext(reference_month="2025-12"),
            "materialized_context_invalid",
        ),
    ],
)
def test_wrong_provider_context_fails_in_a_controlled_way(provider, context, reason):
    with pytest.raises(ContractError) as error:
        provider.produce(context)
    assert error.value.code == ErrorCode.CHAMPION_INPUT_INVALID
    assert error.value.details == {"reason": reason}


def test_factory_selects_one_strategy_without_fallback():
    executable, _ = executable_provider()
    assert isinstance(
        build_champion_output_provider(ChampionProviderStrategy.MATERIALIZED),
        MaterializedChampionProvider,
    )
    assert isinstance(
        build_champion_output_provider("executable", executable_adapter=executable._adapter),
        ExecutableChampionProvider,
    )
    with pytest.raises(ValueError, match="invalid for materialized"):
        build_champion_output_provider("materialized", executable_adapter=executable._adapter)


def test_materialized_provider_failure_never_invokes_executable(materialized_result):
    class ExplodingMaterializedAdapter:
        def from_result(self, result, source_file_sha256=None):
            raise ValueError("invalid configured materialized provider")

    provider = MaterializedChampionProvider(ExplodingMaterializedAdapter())
    with pytest.raises(ValueError, match="invalid configured"):
        provider.produce(
            ChampionExecutionContext(
                reference_month="2025-12", materialized_result=materialized_result
            )
        )


def test_provider_import_has_no_ml_cloud_or_network_dependency():
    script = """
import json
import sys
import api.app.champion.provider
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy', 'pickle')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
