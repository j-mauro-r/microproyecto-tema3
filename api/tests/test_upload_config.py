import pytest

from api.app.core.config import _positive_int, _upload_extensions, get_settings


def test_upload_configuration_parses_safe_overrides() -> None:
    assert _positive_int("2048", "LIMIT") == 2048
    assert _upload_extensions(".CSV, .csv") == (".csv",)
    assert _upload_extensions("") == ()


def test_default_upload_format_is_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOMAC_UPLOAD_ALLOWED_EXTENSIONS", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().upload_allowed_extensions == (".csv",)
    finally:
        get_settings.cache_clear()


def test_database_path_is_configurable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    configured = tmp_path / "configured.sqlite"
    monkeypatch.setenv("BIOMAC_DB_PATH", str(configured))
    get_settings.cache_clear()
    try:
        assert get_settings().db_path == str(configured)
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_upload_limit_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        _positive_int(value, "LIMIT")


@pytest.mark.parametrize("value", ["*", "csv", "../csv"])
def test_upload_allowlist_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        _upload_extensions(value)
