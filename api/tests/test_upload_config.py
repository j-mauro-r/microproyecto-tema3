import pytest

from api.app.core.config import _positive_int, _upload_extensions


def test_upload_configuration_parses_safe_overrides() -> None:
    assert _positive_int("2048", "LIMIT") == 2048
    assert _upload_extensions(".CSV, .csv") == (".csv",)
    assert _upload_extensions("") == ()


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_upload_limit_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        _positive_int(value, "LIMIT")


@pytest.mark.parametrize("value", ["*", "csv", "../csv"])
def test_upload_allowlist_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        _upload_extensions(value)
