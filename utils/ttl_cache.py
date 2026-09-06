"""Small framework-neutral TTL cache used by read services."""

from __future__ import annotations

import functools
import logging
import os
import threading
import time
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")
_clearers: list[tuple[frozenset[str], Callable[[], None]]] = []
_registry_lock = threading.RLock()

# Limites defensivos para evitar crescimento ilimitado de memória no container.
_MAX_CACHE_ENTRIES = int(os.environ.get("BF1_TTL_CACHE_MAX_ENTRIES", "1000"))
_CACHE_EVICTION_BATCH = max(1, _MAX_CACHE_ENTRIES // 10)


def ttl_cache(*, ttl: int, tags: tuple[str, ...] = ()) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        values: dict[object, tuple[float, R]] = {}
        lock = threading.RLock()

        def make_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> object:
            try:
                hash((args, tuple(sorted(kwargs.items()))))
                return args, tuple(sorted(kwargs.items()))
            except TypeError:
                return repr(args), repr(sorted(kwargs.items()))

        def _evict_if_needed() -> None:
            """Remove entradas mais antigas quando o cache excede o limite."""
            if len(values) <= _MAX_CACHE_ENTRIES:
                return
            sorted_items = sorted(values.items(), key=lambda item: item[1][0])
            for old_key, _ in sorted_items[:_CACHE_EVICTION_BATCH]:
                values.pop(old_key, None)
            logger.debug(
                "Cache %s.%s evituiu %s entradas (limite %s)",
                func.__module__, func.__qualname__, _CACHE_EVICTION_BATCH, _MAX_CACHE_ENTRIES,
            )

        def _prune_expired(now: float) -> None:
            """Remove entradas expiradas de forma incremental."""
            expired_keys = [k for k, (expires_at, _) in values.items() if expires_at <= now]
            for k in expired_keys:
                values.pop(k, None)

        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            key = make_key(args, kwargs)
            now = time.monotonic()
            with lock:
                _prune_expired(now)
                cached = values.get(key)
                if cached and cached[0] > now:
                    return cached[1]
            result = func(*args, **kwargs)
            with lock:
                values[key] = (now + ttl, result)
                _evict_if_needed()
            return result

        def clear() -> None:
            with lock:
                values.clear()

        wrapped.clear = clear  # type: ignore[attr-defined]
        cache_tags = frozenset({func.__module__, func.__qualname__, *tags})
        wrapped.cache_tags = cache_tags  # type: ignore[attr-defined]
        with _registry_lock:
            _clearers.append((cache_tags, clear))
        return wrapped
    return decorate


def clear_all_caches(*tags: str) -> None:
    with _registry_lock:
        clearers = tuple(_clearers)
    requested = frozenset(str(tag) for tag in tags if str(tag))
    for cache_tags, clear in clearers:
        if not requested or cache_tags.intersection(requested):
            clear()
