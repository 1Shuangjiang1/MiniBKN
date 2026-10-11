"""Lightweight request trace context used before full event tracing is added."""

from contextvars import ContextVar, Token
from uuid import uuid4

_trace_id: ContextVar[str] = ContextVar("minibkn_trace_id", default="")


def new_trace_id() -> str:
    return f"trace-{uuid4().hex}"


def set_trace_id(value: str) -> Token[str]:
    return _trace_id.set(value)


def reset_trace_id(token: Token[str]) -> None:
    _trace_id.reset(token)


def current_trace_id() -> str:
    return _trace_id.get() or new_trace_id()
