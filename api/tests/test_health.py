from uuid import UUID

from fastapi.testclient import TestClient


EXPECTED_HEALTH = {
    "status": "ok",
    "service": "biomac-api",
    "api_version": "2.0.0",
    "champion_ready": False,
    "storage_ready": False,
}


def test_health_contract_and_truthful_readiness(client: TestClient) -> None:
    response = client.get("/api/v2/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH


def test_each_request_has_an_independent_backend_uuid(client: TestClient) -> None:
    first = client.get("/api/v2/health").headers["X-Request-ID"]
    second = client.get("/api/v2/health").headers["X-Request-ID"]

    assert UUID(first).version == 4
    assert UUID(second).version == 4
    assert first != second


def test_openapi_only_documents_health_for_v2(client: TestClient) -> None:
    response = client.get("/openapi.json")
    paths = response.json()["paths"]

    assert response.status_code == 200
    assert response.json()["info"]["version"] == "2.0.0"
    assert set(paths) == {"/api/v2/health"}


def test_cors_respects_explicit_allowlist(client: TestClient) -> None:
    allowed = client.options(
        "/api/v2/health",
        headers={
            "Origin": "https://dashboard.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v2/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert allowed.headers["access-control-allow-origin"] == "https://dashboard.example.test"
    assert "access-control-allow-origin" not in denied.headers
