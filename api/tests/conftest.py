from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.main import create_app


@pytest.fixture
def configured_app() -> FastAPI:
    return create_app(
        Settings(
            service_name="biomac-api",
            api_version="2.0.0",
            environment="test",
            debug=False,
            cors_origins=("https://dashboard.example.test",),
        )
    )


@pytest.fixture
def client(configured_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(configured_app, raise_server_exceptions=False) as test_client:
        yield test_client
