"""Contexto imutável e isolado por requisição da API."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    client_ip: str | None
    user_id: int | None = None


_context: ContextVar[RequestContext | None] = ContextVar("bf1_api_request", default=None)


def set_request_context(value: RequestContext) -> Token:
    return _context.set(value)


def get_request_context() -> RequestContext | None:
    return _context.get()


def reset_request_context(token: Token) -> None:
    _context.reset(token)

