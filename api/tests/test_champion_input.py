from dataclasses import FrozenInstanceError, replace
import json
import subprocess
import sys

import pytest

from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
    IDENTIFIER_COLUMNS,
    PROHIBITED_INPUT_COLUMNS,
)
from api.app.domain.champion_input import ChampionInputBuilder, MUNICIPALITY_ORDER
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus
from api.tests.test_monthly_upload_validator import csv_bytes


@pytest.fixture
def upload():
    return MonthlyUploadValidator(
        max_bytes=64 * 1024, contract=MonthlyUploadContract()
    ).validate(
        filename="monthly.csv",
        content=csv_bytes(),
        reference_month="2026-01",
        content_type="text/csv",
    )


@pytest.fixture
def builder():
    return ChampionInputBuilder()


def test_builds_framework_agnostic_two_by_thirty_nine_input(builder, upload):
    champion_input = builder.build(upload)
    assert champion_input.municipalities == ("68001", "76001")
    assert champion_input.feature_names is CHAMPION_FEATURES
    assert len(champion_input.rows) == 2
    assert all(len(row) == 39 for row in champion_input.rows)
    assert all(isinstance(value, float) for row in champion_input.rows for value in row)
    with pytest.raises(FrozenInstanceError):
        champion_input.reference_month = "2026-02"


def test_inverted_upload_rows_produce_identical_input(builder, upload):
    inverted = replace(upload, rows=tuple(reversed(upload.rows)))
    assert builder.build(inverted) == builder.build(upload)


def test_feature_order_and_values_are_preserved(builder, upload):
    rows = []
    for municipality_index, source in enumerate(upload.rows, start=1):
        row = dict(source)
        for feature_index, feature in enumerate(CHAMPION_FEATURES, start=1):
            row[feature] = str(municipality_index * 100 + feature_index / 10)
        rows.append(row)
    champion_input = builder.build(replace(upload, rows=tuple(reversed(rows))))
    assert champion_input.feature_names == CHAMPION_FEATURES
    assert champion_input.rows[0][0] == 100.1
    assert champion_input.rows[0][-1] == 103.9
    assert champion_input.rows[1][0] == 200.1
    assert champion_input.rows[1][-1] == 203.9


def test_identifiers_and_targets_are_not_features(builder, upload):
    rows = tuple({**row, "objetivo": "1"} for row in upload.rows)
    feature_names = set(builder.build(replace(upload, rows=rows)).feature_names)
    assert feature_names.isdisjoint(IDENTIFIER_COLUMNS)
    assert feature_names.isdisjoint(PROHIBITED_INPUT_COLUMNS)


def test_preserves_reference_and_contract_traceability(builder, upload):
    champion_input = builder.build(upload)
    assert champion_input.reference_month == upload.reference_month
    assert champion_input.source_file_sha256 == upload.metadata.sha256
    assert champion_input.feature_contract_version == CHAMPION_FEATURE_CONTRACT_VERSION
    assert champion_input.feature_contract_sha256 == CHAMPION_FEATURE_CONTRACT_SHA256


def _rows(upload, municipalities=("68001", "76001")):
    source = {row["divipola"]: dict(row) for row in upload.rows}
    return tuple({**source.get(code, source["68001"]), "divipola": code} for code in municipalities)


@pytest.mark.parametrize(
    ("municipalities", "reason"),
    [
        (("68001",), "municipality_contract_violation"),
        (("68001", "99999"), "municipality_contract_violation"),
        (("68001", "68001"), "duplicate_municipality"),
    ],
)
def test_rejects_inconsistent_municipalities(builder, upload, municipalities, reason):
    with pytest.raises(ContractError) as error:
        builder.build(replace(upload, rows=_rows(upload, municipalities)))
    assert error.value.details["reason"] == reason


def test_rejects_missing_feature(builder, upload):
    rows = [dict(row) for row in upload.rows]
    rows[0].pop(CHAMPION_FEATURES[0])
    with pytest.raises(ContractError) as error:
        builder.build(replace(upload, rows=tuple(rows)))
    assert error.value.details["reason"] == "missing_features"


@pytest.mark.parametrize("value", ["not-numeric", "NaN", "inf", "-inf"])
def test_rejects_invalid_or_non_finite_values(builder, upload, value):
    rows = [dict(row) for row in upload.rows]
    rows[0][CHAMPION_FEATURES[0]] = value
    with pytest.raises(ContractError) as error:
        builder.build(replace(upload, rows=tuple(rows)))
    assert error.value.code == ErrorCode.CHAMPION_INPUT_INVALID
    assert error.value.stage == RunStatus.PREPARING
    assert error.value.details["reason"] == "invalid_feature_values"


@pytest.mark.parametrize("reference_month", ["", "2026-13"])
def test_rejects_invalid_reference_month(builder, upload, reference_month):
    with pytest.raises(ContractError) as error:
        builder.build(replace(upload, reference_month=reference_month))
    assert error.value.stage == RunStatus.PREPARING


def test_rejects_row_period_inconsistent_with_reference(builder, upload):
    rows = [dict(row) for row in upload.rows]
    rows[1]["mes"] = "2"
    with pytest.raises(ContractError) as error:
        builder.build(replace(upload, rows=tuple(rows)))
    assert error.value.details["reason"] == "reference_month_mismatch"


def test_import_does_not_load_ml_cloud_or_dataframe_modules():
    script = """
import json
import sys
import api.app.domain.champion_input
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy', 'pickle')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
