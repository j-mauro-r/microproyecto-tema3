"""Health endpoint contracts."""

from typing import Literal

from api.app.schemas.base import StrictModel


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    api_version: str
    champion_ready: bool
    storage_ready: bool
