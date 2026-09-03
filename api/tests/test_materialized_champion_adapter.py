from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import math
import subprocess
import sys

import pytest

from api.app.champion.materialized import (
    MaterializedChampionPrediction,
    MaterializedChampionResult,
    MaterializedOutputAdapter,
)


@pytest.fixture
def pr12_result():
    predictions = [
        {
            "divipola": "68001", "municipality": "Bucaramanga", "horizon": "T+1",
            "target_month": "2026-01", "probability": 0.61, "threshold": 0.61,
            "label": "EXCESO",
        },
        {
            "divipola": "68001", "municipality": "Bucaramanga", "horizon": "T+2",
            "target_month": "2026-02", "probability": 0.66, "threshold": 0.67,
            "label": "NO_EXCESO",
        },
        {
            "divipola": "76001", "municipality": "Cali", "horizon": "T+1",
            "target_month": "2026-01", "probability": 0.43, "threshold": 0.61,
            "label": "NO_EXCESO",
        },
        {
            "divipola": "76001", "municipality": "Cali", "horizon": "T+2",
            "target_month": "2026-02", "probability": 0.78, "threshold": 0.67,
            "label": "EXCESO",
        },
    ]
    return {
        "model_name": "biomac-champion",
        "model_version": "pr12-example",
        "reference_month": "2025-12",
        "feature_contract_version": "pr12-contract",
        "feature_contract_sha256": "feature-sha",
        "output_type": "probability",
        "predictions": list(reversed(predictions)),
    }


def test_maps_valid_unordered_pr12_result_exactly(pr12_result):
    output = MaterializedOutputAdapter().from_result(pr12_result, "source-sha")
    assert output.reference_month == "2025-12"
    assert output.source_file_sha256 == "source-sha"
    assert output.metadata.name == "biomac-champion"
    assert output.metadata.version == "pr12-example"
    assert output.metadata.feature_contract_version == "pr12-contract"
    assert output.metadata.feature_contract_sha256 == "feature-sha"
    assert output.metadata.output_type == "probability"
    assert output.metadata.supported_horizons == ("T+1", "T+2")
    assert [(p.divipola, p.horizon) for p in output.predictions] == [
        ("68001", "T+1"), ("68001", "T+2"), ("76001", "T+1"), ("76001", "T+2")
    ]
    assert [p.municipality for p in output.predictions] == [
        "Bucaramanga", "Bucaramanga", "Cali", "Cali"
    ]
    assert [p.probability for p in output.predictions] == [0.61, 0.66, 0.43, 0.78]
    assert [p.decision_threshold for p in output.predictions] == [0.61, 0.67, 0.61, 0.67]
    assert [p.label for p in output.predictions] == [
        "EXCESO", "NO_EXCESO", "NO_EXCESO", "EXCESO"
    ]
    assert [p.target_month for p in output.predictions] == [
        "2026-01", "2026-02", "2026-01", "2026-02"
    ]


def test_accepts_internal_immutable_result(pr12_result):
    parsed = MaterializedChampionResult.from_mapping(pr12_result)
    output = MaterializedOutputAdapter().from_result(parsed)
    assert output.source_file_sha256 is None
    with pytest.raises(FrozenInstanceError):
        parsed.model_name = "changed"
    with pytest.raises(FrozenInstanceError):
        parsed.predictions[0].label = "EXCESO"


def test_internal_contract_can_be_constructed_directly(pr12_result):
    parsed = MaterializedChampionResult.from_mapping(pr12_result)
    direct = MaterializedChampionResult(
        model_name=parsed.model_name,
        model_version=parsed.model_version,
        reference_month=parsed.reference_month,
        feature_contract_version=parsed.feature_contract_version,
        feature_contract_sha256=parsed.feature_contract_sha256,
        output_type=parsed.output_type,
        predictions=tuple(
            MaterializedChampionPrediction(
                p.divipola, p.municipality, p.horizon, p.target_month,
                p.probability, p.threshold, p.label,
            )
            for p in parsed.predictions
        ),
    )
    assert MaterializedOutputAdapter().from_result(direct).metadata.name == "biomac-champion"


def test_duplicate_prediction_is_rejected(pr12_result):
    pr12_result["predictions"][0] = deepcopy(pr12_result["predictions"][1])
    with pytest.raises(ValueError, match="duplicate"):
        MaterializedOutputAdapter().from_result(pr12_result)


def test_missing_combination_is_rejected(pr12_result):
    pr12_result["predictions"].pop()
    with pytest.raises(ValueError, match="exact PR12"):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("divipola", "99999", "unsupported municipality"),
        ("horizon", "T+3", "unsupported horizon"),
        ("municipality", "Bogotá", "municipality name"),
    ],
)
def test_unsupported_prediction_identity_is_rejected(pr12_result, field, value, message):
    pr12_result["predictions"][0][field] = value
    with pytest.raises(ValueError, match=message):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("reference_month", ["", "2025-13", "2025-1", "not-a-month"])
def test_invalid_reference_month_is_rejected(pr12_result, reference_month):
    pr12_result["reference_month"] = reference_month
    with pytest.raises(ValueError, match="reference_month"):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("target_month", ["2025-12", "2026-03", "invalid", "2026-13"])
def test_invalid_or_inconsistent_target_month_is_rejected(pr12_result, target_month):
    pr12_result["predictions"][0]["target_month"] = target_month
    with pytest.raises(ValueError, match="target_month"):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("probability", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_invalid_probability_is_rejected(pr12_result, probability):
    pr12_result["predictions"][0]["probability"] = probability
    with pytest.raises(ValueError, match="probability"):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("threshold", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_invalid_threshold_is_rejected(pr12_result, threshold):
    pr12_result["predictions"][0]["threshold"] = threshold
    with pytest.raises(ValueError, match="threshold"):
        MaterializedOutputAdapter().from_result(pr12_result)


def test_inconsistent_label_is_rejected_including_equality_rule(pr12_result):
    # PR12 executable contract defines probability >= threshold as EXCESO.
    equal_prediction = next(
        p for p in pr12_result["predictions"]
        if p["probability"] == p["threshold"]
    )
    equal_prediction["label"] = "NO_EXCESO"
    with pytest.raises(ValueError, match="label is inconsistent"):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("field", ["model_name", "model_version", "output_type"])
def test_missing_or_empty_model_metadata_is_rejected(pr12_result, field):
    pr12_result[field] = ""
    with pytest.raises(ValueError, match=field):
        MaterializedOutputAdapter().from_result(pr12_result)


@pytest.mark.parametrize("field", ["feature_contract_version", "feature_contract_sha256"])
def test_empty_feature_contract_is_rejected(pr12_result, field):
    pr12_result[field] = ""
    with pytest.raises(ValueError, match=field):
        MaterializedOutputAdapter().from_result(pr12_result)


def test_missing_and_unexpected_fields_are_rejected(pr12_result):
    del pr12_result["model_version"]
    pr12_result["unknown"] = "value"
    with pytest.raises(ValueError, match="fields mismatch"):
        MaterializedOutputAdapter().from_result(pr12_result)


def test_materialized_import_has_no_ml_cloud_or_network_dependency():
    script = """
import json
import sys
import api.app.champion.materialized
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy', 'pickle')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
