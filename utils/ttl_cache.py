"""Small framework-neutral TTL cache used by read services."""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
_clearers: list[tuple[frozenset[str], Callable[[], None]]] = []
_registry_lock = threading.RLock()


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

        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            key = make_key(args, kwargs)
            now = time.monotonic()
            with lock:
                cached = values.get(key)
                if cached and cached[0] > now:
                    return cached[1]
            result = func(*args, **kwargs)
            with lock:
                values[key] = (now + ttl, result)
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
