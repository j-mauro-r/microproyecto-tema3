import hashlib

import pytest

from api.app.domain.champion_feature_contract import CHAMPION_FEATURE_CONTRACT_SHA256, CHAMPION_FEATURES
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.schemas.errors import ErrorCode


def csv_bytes(*, year=2026, month=1, municipalities=("68001", "76001"), omit=None,
              invalid_feature=None, extra_column=None, bom=False) -> bytes:
    columns = ["divipola", "anio", "mes", *CHAMPION_FEATURES]
    if omit:
        columns.remove(omit)
    if extra_column:
        columns.append(extra_column)
    lines = [",".join(columns)]
    for municipality in municipalities:
        values = {"divipola": municipality, "anio": str(year), "mes": str(month),
                  **{feature: "1.25" for feature in CHAMPION_FEATURES}}
        if invalid_feature:
            values[invalid_feature] = "not-a-number"
        if extra_column:
            values[extra_column] = "1"
        lines.append(",".join(values[column] for column in columns))
    encoded = ("\n".join(lines) + "\n").encode()
    return b"\xef\xbb\xbf" + encoded if bom else encoded


@pytest.fixture
def validator() -> MonthlyUploadValidator:
    return MonthlyUploadValidator(max_bytes=64 * 1024, contract=MonthlyUploadContract())


@pytest.mark.parametrize(("reference_month", "year", "month"),
                         [("2026-01", 2026, 1), ("2026-12", 2026, 12)])
def test_accepts_valid_january_and_december_csv(validator, reference_month, year, month):
    result = validator.validate(filename="monthly.csv", content=csv_bytes(
        year=year, month=month, bom=month == 12), reference_month=reference_month,
        content_type="text/csv")
    assert result.reference_month == reference_month
    assert tuple(row["divipola"] for row in result.rows) == ("68001", "76001")


@pytest.mark.parametrize("value", ["2026-00", "2026-1", "2026-13", "2026/01", "0000-01"])
def test_rejects_invalid_reference_month(validator, value):
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=csv_bytes(), reference_month=value)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_rejects_empty_oversized_and_non_csv_files(validator):
    cases = (("monthly.csv", b"", "empty_file"),
             ("monthly.csv", b"x" * (64 * 1024 + 1), "file_too_large"),
             ("monthly.xlsx", csv_bytes(), "unsupported_format"))
    for filename, content, reason in cases:
        with pytest.raises(ContractError) as error:
            validator.validate(filename=filename, content=content, reference_month="2026-01")
        assert error.value.details["reason"] == reason


def test_rejects_corrupt_csv(validator):
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=b"value\n\xff\n", reference_month="2026-01")
    assert error.value.details["reason"] == "corrupt_file"


def test_rejects_missing_and_non_numeric_champion_features(validator):
    for content, reason in ((csv_bytes(omit=CHAMPION_FEATURES[0]), "missing_columns"),
                            (csv_bytes(invalid_feature=CHAMPION_FEATURES[0]), "invalid_numeric_features")):
        with pytest.raises(ContractError) as error:
            validator.validate(filename="monthly.csv", content=content, reference_month="2026-01")
        assert error.value.details["reason"] == reason


@pytest.mark.parametrize("invalid_value", ["", "NaN", "inf", "-inf"])
def test_rejects_missing_or_non_finite_feature_values(validator, invalid_value):
    feature = CHAMPION_FEATURES[0]
    content = csv_bytes().decode().replace("1.25", invalid_value, 1).encode()
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=content, reference_month="2026-01")
    assert feature in error.value.details["columns"]


@pytest.mark.parametrize(("municipalities", "reason"), [
    (("76001",), "municipality_contract_violation"),
    (("68001",), "municipality_contract_violation"),
    (("68001", "76001", "99999"), "municipality_contract_violation"),
    (("68001", "68001"), "duplicate_municipality_month"),
])
def test_enforces_exact_municipal_scope(validator, municipalities, reason):
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=csv_bytes(
            municipalities=municipalities), reference_month="2026-01")
    assert error.value.details["reason"] == reason


def test_rejects_any_row_from_another_month(validator):
    lines = csv_bytes().decode().splitlines()
    second_city = lines[2].split(",")
    second_city[2] = "2"
    lines[2] = ",".join(second_city)
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=("\n".join(lines) + "\n").encode(),
                           reference_month="2026-01")
    assert error.value.details["reason"] == "reference_month_mismatch"


@pytest.mark.parametrize("column", ["objetivo", "casos_objetivo", "observed_label"])
def test_rejects_target_or_future_columns(validator, column):
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=csv_bytes(
            extra_column=column), reference_month="2026-01")
    assert error.value.details == {"reason": "prohibited_columns", "columns": [column]}


def test_builds_deterministic_sha256_metadata(validator):
    content = csv_bytes()
    first = validator.validate(filename="../monthly.csv", content=content, reference_month="2026-01")
    second = validator.validate(filename="monthly.csv", content=content, reference_month="2026-01")
    assert first.metadata.original_name == "monthly.csv"
    assert first.metadata.size_bytes == len(content)
    assert first.metadata.sha256 == second.metadata.sha256 == hashlib.sha256(content).hexdigest()
    assert CHAMPION_FEATURE_CONTRACT_SHA256 == "786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba"
