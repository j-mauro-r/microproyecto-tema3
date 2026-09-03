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


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _upload_extensions(value: str) -> tuple[str, ...]:
    extensions = tuple(
        sorted({item.strip().lower() for item in value.split(",") if item.strip()})
    )
    if "*" in extensions:
        raise ValueError("BIOMAC_UPLOAD_ALLOWED_EXTENSIONS must be an explicit allowlist")
    if any(not extension.startswith(".") or "/" in extension for extension in extensions):
        raise ValueError("upload extensions must start with '.' and contain no path")
    return extensions


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str
    api_version: str
    environment: str
    debug: bool
    cors_origins: tuple[str, ...]
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_allowed_extensions: tuple[str, ...] = (".csv",)
    db_path: str = "runtime/biomac.db"


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
        upload_max_bytes=_positive_int(
            os.getenv("BIOMAC_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)),
            "BIOMAC_UPLOAD_MAX_BYTES",
        ),
        upload_allowed_extensions=_upload_extensions(
            os.getenv("BIOMAC_UPLOAD_ALLOWED_EXTENSIONS", ".csv")
        ),
        db_path=os.getenv("BIOMAC_DB_PATH", "runtime/biomac.db"),
    )
