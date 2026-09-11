"""Request-scoped identifiers without shared mutable global state."""

from contextvars import ContextVar, Token
from uuid import UUID, uuid4


_request_id: ContextVar[UUID | None] = ContextVar("request_id", default=None)


def new_request_id() -> tuple[UUID, Token[UUID | None]]:
    request_id = uuid4()
    return request_id, _request_id.set(request_id)


def get_request_id() -> UUID:
    request_id = _request_id.get()
    return request_id if request_id is not None else uuid4()


def reset_request_id(token: Token[UUID | None]) -> None:
    _request_id.reset(token)
