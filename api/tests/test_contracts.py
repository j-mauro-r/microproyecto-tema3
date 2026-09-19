import pytest
from pydantic import ValidationError

from api.app.core.config import _cors_origins
from api.app.schemas.health import HealthResponse
from api.app.schemas.runs import Horizon, RunStatus


def test_strict_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        HealthResponse(
            status="ok",
            service="biomac-api",
            api_version="2.0.0",
            champion_ready=False,
            storage_ready=False,
            invented=True,
        )


@pytest.mark.parametrize("status", [item.value for item in RunStatus])
def test_run_status_accepts_only_catalog_values(status: str) -> None:
    assert RunStatus(status).value == status


def test_invalid_run_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        RunStatus("RUNNING")


def test_horizons_are_limited_to_t1_and_t2() -> None:
    assert {item.value for item in Horizon} == {"T+1", "T+2"}
    with pytest.raises(ValueError):
        Horizon("T+3")


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValueError):
        _cors_origins("*")
