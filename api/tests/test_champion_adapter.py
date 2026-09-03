from dataclasses import FrozenInstanceError, replace

import pytest

from api.app.champion.adapter import (
    LazyChampionAdapter,
    MUNICIPALITY_NAMES,
    NativePrediction,
    build_champion_adapter,
)
from api.app.champion.models import ChampionMetadata, ChampionOutput
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
)
from api.app.domain.champion_input import ChampionInput
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


def metadata(*, horizons=("T+1", "T+2")):
    return ChampionMetadata(
        name="test-champion",
        version="test-only",
        supported_horizons=horizons,
        output_type="probability",
        feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
        feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
    )


@pytest.fixture
def champion_input():
    return ChampionInput(
        reference_month="2026-11",
        municipalities=("68001", "76001"),
        feature_names=CHAMPION_FEATURES,
        rows=(tuple(float(i) for i in range(39)), tuple(float(i) for i in range(39))),
        feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
        feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
        source_file_sha256="source-hash",
    )


class FakeRuntime:
    def __init__(self, champion_metadata, *, fail=False):
        self.metadata = champion_metadata
        self.fail = fail

    def predict(self, inference_input):
        if self.fail:
            raise RuntimeError("secret /internal/model/path")
        probabilities = {"68001": 0.72, "76001": 0.34}
        # Reverse order deliberately: mapping must use explicit keys, never row order.
        return tuple(
            NativePrediction(
                divipola=municipality,
                horizon=horizon,
                probability=probabilities[municipality],
                decision_threshold=0.61,
            )
            for municipality in reversed(inference_input.municipalities)
            for horizon in reversed(self.metadata.supported_horizons)
        )


class CountingLoader:
    def __init__(self, runtime):
        self.runtime = runtime
        self.calls = 0

    def load(self):
        self.calls += 1
        return self.runtime


def test_metadata_contract_and_output_are_immutable(champion_input):
    champion_metadata = metadata()
    adapter = LazyChampionAdapter(CountingLoader(FakeRuntime(champion_metadata)))
    output = adapter.predict(champion_input)
    assert adapter.metadata() is champion_metadata
    assert isinstance(output, ChampionOutput)
    with pytest.raises(FrozenInstanceError):
        output.reference_month = "2027-01"


def test_valid_two_by_thirty_nine_input_maps_bucaramanga_and_cali(champion_input):
    assert MUNICIPALITY_NAMES == {"68001": "Bucaramanga", "76001": "Cali"}
    output = LazyChampionAdapter(CountingLoader(FakeRuntime(metadata()))).predict(champion_input)
    assert [(item.divipola, item.horizon) for item in output.predictions] == [
        ("68001", "T+1"), ("68001", "T+2"), ("76001", "T+1"), ("76001", "T+2")
    ]
    assert [item.target_month for item in output.predictions[:2]] == ["2026-12", "2027-01"]
    assert [item.probability for item in output.predictions] == [0.72, 0.72, 0.34, 0.34]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("feature_contract_version", "other", "feature_contract_version_mismatch"),
        ("feature_contract_sha256", "other", "feature_contract_sha256_mismatch"),
    ],
)
def test_feature_contract_mismatch_blocks_inference(champion_input, field, value, reason):
    adapter = LazyChampionAdapter(CountingLoader(FakeRuntime(metadata())))
    with pytest.raises(ContractError) as error:
        adapter.predict(replace(champion_input, **{field: value}))
    assert error.value.code == ErrorCode.CHAMPION_INPUT_INVALID
    assert error.value.stage == RunStatus.PREPARING
    assert error.value.details == {"reason": reason}


def test_t1_only_champion_never_creates_t2(champion_input):
    output = LazyChampionAdapter(
        CountingLoader(FakeRuntime(metadata(horizons=("T+1",))))
    ).predict(champion_input)
    assert [(item.divipola, item.horizon) for item in output.predictions] == [
        ("68001", "T+1"), ("76001", "T+1")
    ]


def test_prediction_threshold_is_preserved_and_drives_label(champion_input):
    output = LazyChampionAdapter(CountingLoader(FakeRuntime(metadata()))).predict(
        champion_input
    )
    assert [item.decision_threshold for item in output.predictions] == [0.61] * 4
    assert [item.label for item in output.predictions] == [
        "EXCESO", "EXCESO", "NO_EXCESO", "NO_EXCESO"
    ]


def test_missing_threshold_does_not_fabricate_threshold_or_label(champion_input):
    class ThresholdlessRuntime(FakeRuntime):
        def predict(self, inference_input):
            return tuple(
                NativePrediction(divipola=municipality, horizon=horizon, probability=0.72)
                for municipality in inference_input.municipalities
                for horizon in self.metadata.supported_horizons
            )

    output = LazyChampionAdapter(CountingLoader(ThresholdlessRuntime(metadata()))).predict(champion_input)
    assert all(item.decision_threshold is None and item.label is None for item in output.predictions)


def test_non_probability_output_does_not_fabricate_probability(champion_input):
    class ExpectedCasesRuntime:
        metadata = replace(metadata(), output_type="expected_cases")

        def predict(self, inference_input):
            return tuple(
                NativePrediction(divipola=municipality, horizon=horizon, expected_cases=12.5)
                for municipality in inference_input.municipalities
                for horizon in self.metadata.supported_horizons
            )

    output = LazyChampionAdapter(CountingLoader(ExpectedCasesRuntime())).predict(champion_input)
    assert all(item.expected_cases == 12.5 for item in output.predictions)
    assert all(item.probability is None for item in output.predictions)


def test_missing_production_champion_is_not_ready(champion_input):
    with pytest.raises(ContractError) as error:
        build_champion_adapter().predict(champion_input)
    assert error.value.code == ErrorCode.CHAMPION_NOT_READY
    assert error.value.stage == RunStatus.INFERENCING
    assert "path" not in error.value.message


def test_runtime_failure_is_sanitized(champion_input):
    adapter = LazyChampionAdapter(CountingLoader(FakeRuntime(metadata(), fail=True)))
    with pytest.raises(ContractError) as error:
        adapter.predict(champion_input)
    assert error.value.code == ErrorCode.INFERENCE_FAILED
    assert error.value.stage == RunStatus.INFERENCING
    assert "internal" not in error.value.message.lower()
    assert error.value.details == {"reason": "champion_execution_failed"}


def test_runtime_is_loaded_once_per_adapter(champion_input):
    loader = CountingLoader(FakeRuntime(metadata()))
    adapter = LazyChampionAdapter(loader)
    adapter.metadata()
    adapter.predict(champion_input)
    adapter.predict(champion_input)
    assert loader.calls == 1
