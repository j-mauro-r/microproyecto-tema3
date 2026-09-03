import hashlib

import pytest

from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.schemas.errors import ErrorCode


def _validator(**contract_overrides: object) -> MonthlyUploadValidator:
    contract = MonthlyUploadContract(allowed_extensions=(".csv",), **contract_overrides)
    return MonthlyUploadValidator(max_bytes=1024, contract=contract)


@pytest.mark.parametrize("value", ["2026-1", "26-01", "2026/01", "2026-13", "0000-01"])
def test_rejects_invalid_reference_month(value: str) -> None:
    with pytest.raises(ContractError) as error:
        _validator().validate(filename="monthly.csv", content=b"value\n1\n", reference_month=value)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_rejects_empty_oversized_and_unsupported_files() -> None:
    validator = _validator()
    for filename, content, reason in (
        ("monthly.csv", b"", "empty_file"),
        ("monthly.csv", b"x" * 1025, "file_too_large"),
        ("monthly.xlsx", b"value\n1\n", "unsupported_format"),
    ):
        with pytest.raises(ContractError) as error:
            validator.validate(filename=filename, content=content, reference_month="2026-01")
        assert error.value.details["reason"] == reason


def test_fails_closed_when_repository_has_no_format_contract() -> None:
    validator = MonthlyUploadValidator(max_bytes=1024, contract=MonthlyUploadContract())
    with pytest.raises(ContractError) as error:
        validator.validate(filename="monthly.csv", content=b"value\n1\n", reference_month="2026-01")
    assert error.value.details["reason"] == "format_contract_missing"


def test_builds_sha256_metadata_without_writing_or_external_services() -> None:
    content = b"value\n1\n"
    result = _validator().validate(
        filename="../monthly.csv",
        content=content,
        reference_month="2026-01",
        content_type="text/csv",
    )
    assert result.metadata.original_name == "monthly.csv"
    assert result.metadata.size_bytes == len(content)
    assert result.metadata.sha256 == hashlib.sha256(content).hexdigest()
    assert result.content == content
    other = _validator().validate(
        filename="monthly.csv", content=b"value\n2\n", reference_month="2026-01"
    )
    assert other.metadata.sha256 != result.metadata.sha256


def test_corrupt_csv_is_a_controlled_error() -> None:
    with pytest.raises(ContractError) as error:
        _validator().validate(
            filename="monthly.csv", content=b"value\n\xff\n", reference_month="2026-01"
        )
    assert error.value.details["reason"] == "corrupt_file"


def test_configured_structure_period_and_municipality_rules() -> None:
    validator = _validator(
        required_columns=("period", "divipola", "value"),
        temporal_column="period",
        municipality_column="divipola",
        required_municipalities=("68001", "76001"),
    )
    valid = b"period,divipola,value\n2026-01,68001,1\n2026-01,76001,2\n"
    assert validator.validate(filename="x.csv", content=valid, reference_month="2026-01")

    invalid_cases = (
        (b"period,divipola\n2026-01,68001\n", "missing_columns"),
        (b"period,divipola,value\n2026-02,68001,1\n", "reference_month_mismatch"),
        (b"period,divipola,value\n2026-01,99999,1\n", "municipality_contract_violation"),
    )
    for content, reason in invalid_cases:
        with pytest.raises(ContractError) as error:
            validator.validate(filename="x.csv", content=content, reference_month="2026-01")
        assert error.value.details["reason"] == reason
