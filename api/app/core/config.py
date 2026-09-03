"""Environment-backed, non-sensitive API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


API_VERSION = "2.0.0"
API_PREFIX = "/api/v2"


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _cors_origins(value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
    if "*" in origins:
        raise ValueError("BIOMAC_CORS_ORIGINS must be an explicit allowlist")
    return origins


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str
    api_version: str
    environment: str
    debug: bool
    cors_origins: tuple[str, ...]


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process from defaults and environment variables."""
    return Settings(
        service_name=os.getenv("BIOMAC_SERVICE_NAME", "biomac-api"),
        api_version=API_VERSION,
        environment=os.getenv("BIOMAC_ENVIRONMENT", "local"),
        debug=_as_bool(os.getenv("BIOMAC_DEBUG", "false")),
        cors_origins=_cors_origins(
            os.getenv(
                "BIOMAC_CORS_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://localhost:8050",
            )
        ),
    )
