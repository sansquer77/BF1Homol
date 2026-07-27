"""Framework-neutral request context populated by the delivery layer."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, MutableMapping

_fallback_session: dict[str, Any] = {}
_session: ContextVar[MutableMapping[str, Any]] = ContextVar("bf1_session", default=_fallback_session)
_headers: ContextVar[object] = ContextVar("bf1_request_headers", default={})
_direct_ip: ContextVar[object] = ContextVar("bf1_direct_ip", default=None)


def bind_runtime(session: MutableMapping[str, Any], *, headers: object = None, direct_ip: object = None) -> None:
    _session.set(session)
    _headers.set(headers or {})
    _direct_ip.set(direct_ip)


def get_session() -> MutableMapping[str, Any]:
    return _session.get()


def get_request_metadata() -> tuple[object, object]:
    return _headers.get(), _direct_ip.get()
