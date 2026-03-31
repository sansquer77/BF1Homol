"""Pool de conexões PostgreSQL nativo com dict_row."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

try:
    import streamlit as st
except Exception:  # no cover - fallback para execução fora do Streamlit
    st = None

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool as PsycopgConnectionPool

from db.db_config import (
    DATABASE_URL,
    DB_CONN_MAX_LIFETIME,
    DB_MAX_CONN,
    DB_MIN_CONN,
    DB_TIMEOUT,
)


class ConnectionPool:
    """Pool de conexões thread-safe para PostgreSQL."""

    def __init__(self, pool_size: int = 5, timeout: float = 30.0) -> None:
        self.pool_size = pool_size
        self.timeout = timeout
        self._pg_pool: Optional[PsycopgConnectionPool] = None
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Inicializa recursos do backend PostgreSQL."""
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL não configurada para backend PostgreSQL")
        self._pg_pool = PsycopgConnectionPool(
            conninfo=DATABASE_URL,
            min_size=DB_MIN_CONN,
            max_size=DB_MAX_CONN,
            max_lifetime=DB_CONN_MAX_LIFETIME,
            timeout=self.timeout,
            kwargs={"autocommit": False, "row_factory": dict_row},
            open=True,
        )

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        """Retorna conexão do pool como context manager."""
        if self._pg_pool is None:
            self._initialize_pool()
        if self._pg_pool is None:
            raise RuntimeError("Pool PostgreSQL não inicializado")
        with self._pg_pool.connection() as conn:
            yield conn

    def close_all(self) -> None:
        """Fecha todas as conexões do pool."""
        if self._pg_pool is not None:
            self._pg_pool.close()
            self._pg_pool = None


# Instância global do pool
_pool: Optional[ConnectionPool] = None

def _build_pool(pool_size: int) -> ConnectionPool:
    return ConnectionPool(pool_size, DB_TIMEOUT)


if st is not None:

    @st.cache_resource(show_spinner=False)
    def _get_cached_pool(pool_size: int) -> ConnectionPool:
        return _build_pool(pool_size)

else:

    def _get_cached_pool(pool_size: int) -> ConnectionPool:
        return _build_pool(pool_size)


def init_pool(pool_size: int = 5) -> None:
    """Inicializa o pool global."""
    global _pool
    _pool = _get_cached_pool(pool_size)

def get_pool() -> ConnectionPool:
    """Retorna o pool global."""
    global _pool
    if _pool is None:
        init_pool(pool_size=5)
    return _pool

def close_pool() -> None:
    """Fecha o pool global."""
    global _pool
    if _pool:
        _pool.close_all()
        _pool = None
