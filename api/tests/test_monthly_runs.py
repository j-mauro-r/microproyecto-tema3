from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app


def _app(contract: MonthlyUploadContract | None = None, max_bytes: int = 1024) -> FastAPI:
    settings = Settings(
        service_name="biomac-api",
        api_version="2.0.0",
        environment="test",
        debug=False,
        cors_origins=("https://dashboard.example.test",),
        upload_max_bytes=max_bytes,
    )
    validator = MonthlyUploadValidator(max_bytes=max_bytes, contract=contract or MonthlyUploadContract())
    return create_app(settings, monthly_upload_validator=validator)


def test_default_endpoint_fails_closed_without_invented_format() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v2/monthly-runs",
            data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", b"value\n1\n", "text/csv")},
        )
    detail = response.json()["error"]
    assert response.status_code == 422
    assert detail["code"] == "INVALID_UPLOAD"
    assert detail["stage"] == "VALIDATING"
    assert UUID(detail["request_id"])
    assert response.headers["X-Request-ID"] == detail["request_id"]


def test_valid_configured_upload_does_not_fabricate_201_completed() -> None:
    with TestClient(
        _app(MonthlyUploadContract(allowed_extensions=(".csv",))),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/api/v2/monthly-runs",
            data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", b"value\n1\n", "text/csv")},
        )
    detail = response.json()["error"]
    assert response.status_code == 503
    assert detail["code"] == "CHAMPION_NOT_READY"
    assert detail["stage"] == "VALIDATING"
    assert len(detail["details"]["source_file"]["sha256"]) == 64


def test_http_boundary_enforces_size_without_reading_unbounded_payload() -> None:
    with TestClient(
        _app(MonthlyUploadContract(allowed_extensions=(".csv",)), max_bytes=5),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/api/v2/monthly-runs",
            data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", b"value\n1\n", "text/csv")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason"] == "file_too_large"


def test_cors_preflight_allows_monthly_post() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.options(
            "/api/v2/monthly-runs",
            headers={
                "Origin": "https://dashboard.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]

    with TestClient(_app(), raise_server_exceptions=False) as client:
        denied = client.options(
            "/api/v2/monthly-runs",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert "access-control-allow-origin" not in denied.headers
