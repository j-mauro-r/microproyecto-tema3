from uuid import UUID

from fastapi import Body, FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.app.schemas.health import HealthResponse


def _add_error_routes(app: FastAPI) -> None:
    @app.post("/_test/contract")
    async def contract(payload: HealthResponse = Body()) -> HealthResponse:
        return payload

    @app.get("/_test/controlled")
    async def controlled() -> None:
        raise HTTPException(status_code=400, detail="Petición controlada")

    @app.get("/_test/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("SECRET_VALUE /private/internal/path")


def test_validation_error_uses_contractual_envelope(configured_app: FastAPI) -> None:
    _add_error_routes(configured_app)
    with TestClient(configured_app, raise_server_exceptions=False) as client:
        response = client.post("/_test/contract", json={"unknown": True})

    detail = response.json()["error"]
    assert response.status_code == 422
    assert detail["code"] == "INVALID_REQUEST"
    assert UUID(detail["request_id"])
    assert detail["run_id"] is None
    assert detail["stage"] is None


def test_http_exception_uses_contractual_envelope(configured_app: FastAPI) -> None:
    _add_error_routes(configured_app)
    with TestClient(configured_app, raise_server_exceptions=False) as client:
        response = client.get("/_test/controlled")

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Petición controlada"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]


def test_unexpected_error_is_sanitized(configured_app: FastAPI) -> None:
    _add_error_routes(configured_app)
    with TestClient(configured_app, raise_server_exceptions=False) as client:
        response = client.get("/_test/unexpected")

    body = response.text
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "SECRET_VALUE" not in body
    assert "/private/internal/path" not in body
    assert "Traceback" not in body
