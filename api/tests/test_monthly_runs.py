from uuid import UUID

from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.main import create_app
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus
from api.tests.test_persistence import _ready, _service
from api.tests.test_monthly_upload_validator import csv_bytes


def _app(max_bytes=64 * 1024):
    return create_app(Settings(service_name="biomac-api", api_version="2.0.0",
        environment="test", debug=False, cors_origins=("https://dashboard.example.test",),
        upload_max_bytes=max_bytes))


def test_valid_upload_does_not_fabricate_201_completed():
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", csv_bytes(), "text/csv")})
    detail = response.json()["error"]
    assert response.status_code == 503
    assert detail["code"] == "PERSISTENCE_FAILED"
    assert detail["stage"] == "PERSISTING"
    assert detail["details"]["reason"] == "durable_persistence_not_available"
    assert len(detail["details"]["source_file"]["sha256"]) == 64
    assert "prediction" not in response.text.lower()


def test_invalid_upload_has_contractual_request_id():
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", b"", "text/csv")})
    detail = response.json()["error"]
    assert response.status_code == 422
    assert detail["code"] == "INVALID_UPLOAD" and detail["stage"] == "VALIDATING"
    assert UUID(detail["request_id"])
    assert response.headers["X-Request-ID"] == detail["request_id"]


def test_http_boundary_enforces_size_without_unbounded_read():
    with TestClient(_app(max_bytes=5), raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
            files={"file": ("monthly.csv", csv_bytes(), "text/csv")})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason"] == "file_too_large"


def test_cors_preflight_allows_configured_origin_only():
    with TestClient(_app(), raise_server_exceptions=False) as client:
        allowed = client.options("/api/v2/monthly-runs", headers={
            "Origin": "https://dashboard.example.test", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"})
        denied = client.options("/api/v2/monthly-runs", headers={
            "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert allowed.status_code == 200 and "POST" in allowed.headers["access-control-allow-methods"]
    assert allowed.headers["access-control-allow-origin"] == "https://dashboard.example.test"
    assert "access-control-allow-origin" not in denied.headers


class _Orchestrator:
    def run(self, command):
        return _ready()


class _BrokenPersistence:
    def persist(self, result):
        raise ContractError(
            ErrorCode.PERSISTENCE_FAILED, "No fue posible persistir el run mensual.",
            status_code=500, stage=RunStatus.PERSISTING,
            details={"reason": "sqlite_transaction_failed"},
        )


def test_valid_post_returns_201_only_with_durable_completed_result(tmp_path):
    app = create_app(
        Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                 debug=False, cors_origins=()),
        monthly_orchestrator=_Orchestrator(),
        persistence_service=_service(tmp_path / "biomac.db"),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
                               files={"file": ("monthly.csv", csv_bytes(), "text/csv")})
    body = response.json()
    assert response.status_code == 201
    assert body["run"]["status"] == "COMPLETED"
    assert body["run"]["completed_at"] is not None
    assert len(body["prediction_snapshot"]["predictions"]) == 4


def test_composition_uses_configured_database_path(tmp_path):
    path = tmp_path / "configured.sqlite"
    app = create_app(
        Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                 debug=False, cors_origins=(), db_path=str(path)),
        monthly_orchestrator=_Orchestrator(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
                               files={"file": ("monthly.csv", csv_bytes(), "text/csv")})
    assert response.status_code == 201 and path.exists()


def test_database_failure_returns_sanitized_persistence_error():
    app = create_app(
        Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                 debug=False, cors_origins=()),
        monthly_orchestrator=_Orchestrator(), persistence_service=_BrokenPersistence(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v2/monthly-runs", data={"reference_month": "2026-01"},
                               files={"file": ("monthly.csv", csv_bytes(), "text/csv")})
    error = response.json()["error"]
    assert response.status_code == 500
    assert error["code"] == "PERSISTENCE_FAILED" and error["stage"] == "PERSISTING"
    assert "sqlite" not in error["message"].lower()
