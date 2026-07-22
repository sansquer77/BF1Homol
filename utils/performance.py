"""Observabilidade de jornadas, banco e cache.

As metricas sao emitidas como JSON no logger ``bf1.performance`` para serem
coletadas pelo provedor de logs da aplicacao.
"""

from __future__ import annotations

import contextvars
import functools
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, ParamSpec, TypeVar

logger = logging.getLogger("bf1.performance")
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class JourneyMetrics:
    name: str
    started: float = field(default_factory=time.perf_counter)
    queries: int = 0
    db_seconds: float = 0.0
    rows: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    query_fingerprints: dict[str, int] = field(default_factory=dict)


_current: contextvars.ContextVar[JourneyMetrics | None] = contextvars.ContextVar(
    "bf1_current_journey", default=None
)
_cache_miss_serial: contextvars.ContextVar[int] = contextvars.ContextVar(
    "bf1_cache_miss_serial", default=0
)


def _fingerprint(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", sql).strip()
    normalized = re.sub(r"'(?:''|[^'])*'|\b\d+\b", "?", normalized)
    return normalized[:240]


def record_query(sql: str, elapsed: float) -> None:
    metrics = _current.get()
    if metrics is None:
        return
    metrics.queries += 1
    metrics.db_seconds += elapsed
    key = _fingerprint(sql)
    metrics.query_fingerprints[key] = metrics.query_fingerprints.get(key, 0) + 1


def record_rows(count: int) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.rows += max(0, int(count))


def record_cache(hit: bool) -> None:
    metrics = _current.get()
    if metrics is not None:
        if hit:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1


class journey:
    """Context manager que mede uma jornada completa (suporta aninhamento)."""

    def __init__(self, name: str, **dimensions: Any) -> None:
        self.name = name
        self.dimensions = dimensions
        self.metrics: JourneyMetrics | None = None
        self.token = None
        self.owner = False

    def __enter__(self) -> JourneyMetrics:
        existing = _current.get()
        if existing is not None:
            return existing
        self.owner = True
        self.metrics = JourneyMetrics(self.name)
        self.token = _current.set(self.metrics)
        return self.metrics

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.owner or self.metrics is None:
            return
        elapsed = time.perf_counter() - self.metrics.started
        control_flow = exc_type is not None and exc_type.__name__ in {"RerunException", "StopException"}
        payload = {
            "event": "journey_performance",
            "journey": self.metrics.name,
            "duration_ms": round(elapsed * 1000, 2),
            "query_count": self.metrics.queries,
            "db_time_ms": round(self.metrics.db_seconds * 1000, 2),
            "rows_processed": self.metrics.rows,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "success": exc_type is None or control_flow,
            "query_fingerprints": self.metrics.query_fingerprints,
            **self.dimensions,
        }
        logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if self.token is not None:
            _current.reset(self.token)


def measured(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with journey(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def instrumented_cache_data(*, ttl: int):
    """Substituto observavel para ``st.cache_data``.

    O corpo interno roda somente no miss; a chamada externa registra o hit.
    """
    import streamlit as st

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        # Todos os wrappers abaixo compartilham a mesma implementação interna.
        # O namespace explícito impede o Streamlit de reutilizar o valor de uma
        # função em outra quando ambas recebem argumentos iguais (ex.: temporada).
        cache_namespace = f"{func.__module__}.{func.__qualname__}"

        @st.cache_data(ttl=ttl, show_spinner=False)
        def cached(namespace: str, *args: P.args, **kwargs: P.kwargs) -> R:
            record_cache(hit=False)
            _cache_miss_serial.set(_cache_miss_serial.get() + 1)
            return func(*args, **kwargs)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            serial_before = _cache_miss_serial.get()
            value = cached(cache_namespace, *args, **kwargs)
            if _cache_miss_serial.get() == serial_before:
                record_cache(hit=True)
            return value

        wrapper.clear = cached.clear  # type: ignore[attr-defined]
        return wrapper
    return decorator


def performance_enabled() -> bool:
    return os.environ.get("PERFORMANCE_METRICS_ENABLED", "1").lower() not in {"0", "false", "no"}
