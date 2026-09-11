import inspect
import json
import subprocess
import sys

import pytest

from api.app.champion.adapter import LazyChampionAdapter, NativePrediction
from api.app.champion.models import ChampionMetadata, ChampionOutput
from api.app.champion.provider import ExecutableChampionProvider
from api.app.champion.service import (
    CallableMaterializedChampionResultProvider,
    ChampionOperationalContext,
    ChampionService,
    build_champion_service,
)
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
)
from api.app.domain.champion_input import ChampionInput
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode


def pr12_result(**overrides):
    result = {
        "model_name": "biomac-champion",
        "model_version": "service-test",
        "reference_month": "2025-12",
        "feature_contract_version": CHAMPION_FEATURE_CONTRACT_VERSION,
        "feature_contract_sha256": CHAMPION_FEATURE_CONTRACT_SHA256,
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
    result.update(overrides)
    return result


def executable_input():
    return ChampionInput(
        reference_month="2025-12",
        municipalities=("68001", "76001"),
        feature_names=CHAMPION_FEATURES,
        rows=(tuple([1.0] * 39), tuple([2.0] * 39)),
        feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
        feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
        source_file_sha256="source-sha",
    )


class CountingInputProvider:
    def __init__(self):
        self.calls = 0

    def get_input(self, context):
        self.calls += 1
        return executable_input()


class CountingRuntimeLoader:
    def __init__(self, *, fail=False):
        self.calls = 0
        self.fail = fail

    def load(self):
        self.calls += 1
        fail = self.fail

        class Runtime:
            metadata = ChampionMetadata(
                name="executable-service-test",
                version="1.0.0",
                supported_horizons=("T+1",),
                output_type="probability",
                feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
                feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
            )

            def predict(self, inference_input):
                if fail:
                    raise RuntimeError("configured executable failed")
                return tuple(
                    NativePrediction(
                        divipola=code,
                        horizon="T+1",
                        probability=0.7,
                        decision_threshold=0.63,
                    )
                    for code in inference_input.municipalities
                )

        return Runtime()


def executable_service(*, fail=False):
    input_provider = CountingInputProvider()
    loader = CountingRuntimeLoader(fail=fail)
    service = build_champion_service(
        "executable",
        executable_input_provider=input_provider,
        executable_output_provider=ExecutableChampionProvider(LazyChampionAdapter(loader)),
    )
    return service, input_provider, loader


def materialized_service(resolver=pr12_result):
    calls = []

    def tracked(reference_month):
        calls.append(reference_month)
        return resolver()

    service = build_champion_service(
        "materialized",
        materialized_result_provider=CallableMaterializedChampionResultProvider(tracked),
    )
    return service, calls


def consume_like_hu005(service: ChampionService, context: ChampionOperationalContext):
    return service.produce(context)


def test_hu005_style_consumer_is_provider_neutral_and_import_free():
    source = inspect.getsource(consume_like_hu005)
    assert "ChampionInput" not in source
    assert "MaterializedChampionResult" not in source
    assert "ProviderStrategy" not in source
    assert "produce(context)" in source


def test_same_consumer_produces_same_output_type_for_both_strategies():
    materialized, _ = materialized_service()
    executable, _, _ = executable_service()
    context = ChampionOperationalContext("2025-12", "source-sha")
    outputs = [
        consume_like_hu005(materialized, context),
        consume_like_hu005(executable, context),
    ]
    assert all(type(output) is ChampionOutput for output in outputs)
    assert all(output.reference_month == "2025-12" for output in outputs)
    assert all(output.source_file_sha256 == "source-sha" for output in outputs)


def test_materialized_strategy_resolves_result_internally_and_preserves_thresholds():
    service, calls = materialized_service()
    output = service.produce(ChampionOperationalContext("2025-12", "source-sha"))
    assert calls == ["2025-12"]
    assert [prediction.decision_threshold for prediction in output.predictions] == [
        0.61, 0.67, 0.61, 0.67
    ]


@pytest.mark.parametrize(
    ("overrides", "mismatched_fields"),
    [
        ({"feature_contract_version": "other"}, {"received_version": "other"}),
        ({"feature_contract_sha256": "other"}, {"received_sha256": "other"}),
        (
            {"feature_contract_version": "other", "feature_contract_sha256": "other"},
            {"received_version": "other", "received_sha256": "other"},
        ),
    ],
)
def test_materialized_feature_contract_gate_rejects_every_mismatch(
    overrides, mismatched_fields
):
    service, _ = materialized_service(lambda: pr12_result(**overrides))
    with pytest.raises(ContractError) as error:
        service.produce(ChampionOperationalContext("2025-12", "source-sha"))
    assert error.value.code is ErrorCode.CHAMPION_INPUT_INVALID
    assert error.value.details["reason"] == "feature_contract_mismatch"
    assert error.value.details["expected_version"] == CHAMPION_FEATURE_CONTRACT_VERSION
    assert error.value.details["expected_sha256"] == CHAMPION_FEATURE_CONTRACT_SHA256
    assert error.value.details.items() >= mismatched_fields.items()


def test_executable_strategy_resolves_input_internally_and_keeps_load_once():
    service, input_provider, loader = executable_service()
    context = ChampionOperationalContext("2025-12", "source-sha")
    service.produce(context)
    service.produce(context)
    assert input_provider.calls == 2
    assert loader.calls == 1


def test_composition_rejects_mixed_strategy_dependencies():
    executable, input_provider, _ = executable_service()
    with pytest.raises(ValueError, match="executable dependencies"):
        build_champion_service(
            "materialized",
            materialized_result_provider=CallableMaterializedChampionResultProvider(
                lambda _: pr12_result()
            ),
            executable_input_provider=input_provider,
            executable_output_provider=executable._output_provider,
        )


def test_materialized_failure_does_not_activate_executable():
    executable_calls = []

    def fail():
        raise RuntimeError("materialized source unavailable")

    service, _ = materialized_service(fail)
    with pytest.raises(ContractError) as error:
        service.produce(ChampionOperationalContext("2025-12"))
    assert error.value.code == ErrorCode.CHAMPION_NOT_READY
    assert error.value.details == {"reason": "materialized_result_unavailable"}
    assert executable_calls == []


def test_executable_failure_does_not_activate_materialized():
    service, _, _ = executable_service(fail=True)
    materialized_calls = []
    with pytest.raises(Exception) as error:
        service.produce(ChampionOperationalContext("2025-12", "source-sha"))
    assert "inferencia" in str(error.value).lower()
    assert materialized_calls == []


def test_service_import_has_no_ml_cloud_or_network_dependency():
    script = """
import json
import sys
import api.app.champion.service
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy', 'pickle')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
