from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class RequestContext:
    request_id: str
    project_id: str | None = None
    token_id: str | None = None
    plan: str | None = None
    scopes: tuple[str, ...] = ()
    tool_name: str | None = None
    db_name: str | None = None
    idempotency_key: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def set_request_context(context: RequestContext):
    return _request_context.set(context)


def reset_request_context(token) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    return _request_context.get()
