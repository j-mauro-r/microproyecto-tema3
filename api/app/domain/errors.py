"""Domain failures that can be mapped to the public API contract."""

from dataclasses import dataclass, field
from http import HTTPStatus

from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


@dataclass(frozen=True, slots=True)
class ContractError(Exception):
    code: ErrorCode
    message: str
    status_code: int = HTTPStatus.UNPROCESSABLE_ENTITY
    stage: RunStatus = RunStatus.VALIDATING
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
