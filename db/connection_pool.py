import logging
import re
import threading
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extensions
import psycopg2.extras

from db.db_config import DATABASE_URL

logger = logging.getLogger(__name__)


def _normalize_sql_for_postgres(sql: str) -> str:
    """Valida que o SQL é nativo PostgreSQL — sem placeholders legados ou construções SQLite.

    Rejeita '?' (deve usar '%s') e 'INSERT OR REPLACE' (deve usar ON CONFLICT).
    Todo SQL deve ser escrito em PostgreSQL nativo — esta função não faz conversões.
    """
    if re.search(r"(?<![!<>=])\?", sql):
        raise ValueError(
            "Placeholder '?' detectado. Use SQL nativo PostgreSQL com '%s'. "
            f"SQL ofensivo: {sql[:120]!r}"
        )
    if re.match(r"^\s*INSERT\s+OR\s+REPLACE\s+", sql, re.IGNORECASE):
        raise ValueError(
            "INSERT OR REPLACE não é suportado no PostgreSQL. "
            "Use INSERT ... ON CONFLICT (...) DO UPDATE SET ... no lugar."
        )
    return sql


class ConnectionPool:
    """Pool de conexões PostgreSQL thread-safe com reconexão automática."""

    def __init__(
        self,
        database_url: str,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,
    ) -> None:
        self._database_url = database_url
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._connection_timeout = connection_timeout
        self._idle_timeout = idle_timeout

        self._pool: list[psycopg2.extensions.connection] = []
        self._in_use: set[int] = set()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._last_used: dict[int, float] = {}
        self._closed = False

        self._initialize_pool()
        self._start_idle_cleanup()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _create_connection(self) -> psycopg2.extensions.connection:
        conn = psycopg2.connect(
            self._database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
            connect_timeout=10,
        )
        conn.autocommit = False
        return conn

    def _initialize_pool(self) -> None:
        for _ in range(self._min_connections):
            try:
                conn = self._create_connection()
                self._pool.append(conn)
                self._last_used[id(conn)] = time.monotonic()
            except Exception as exc:
                logger.warning("Pool init: could not create connection: %s", exc)

    def _is_connection_alive(self, conn: psycopg2.extensions.connection) -> bool:
        try:
            conn.cursor().execute("SELECT 1")
            return True
        except Exception:
            return False

    def _start_idle_cleanup(self) -> None:
        t = threading.Thread(target=self._idle_cleanup_loop, daemon=True)
        t.start()

    def _idle_cleanup_loop(self) -> None:
        while not self._closed:
            time.sleep(60)
            self._cleanup_idle_connections()

    def _cleanup_idle_connections(self) -> None:
        now = time.monotonic()
        with self._lock:
            to_close = [
                conn
                for conn in list(self._pool)
                if id(conn) not in self._in_use
                and now - self._last_used.get(id(conn), now) > self._idle_timeout
                and len(self._pool) > self._min_connections
            ]
            for conn in to_close:
                self._pool.remove(conn)
                self._last_used.pop(id(conn), None)
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def acquire(self) -> psycopg2.extensions.connection:
        deadline = time.monotonic() + self._connection_timeout
        with self._condition:
            while True:
                for conn in self._pool:
                    if id(conn) not in self._in_use:
                        if not self._is_connection_alive(conn):
                            self._pool.remove(conn)
                            self._last_used.pop(id(conn), None)
                            try:
                                conn.close()
                            except Exception:
                                pass
                            try:
                                conn = self._create_connection()
                                self._pool.append(conn)
                            except Exception as exc:
                                raise RuntimeError(f"Failed to reconnect: {exc}") from exc
                        self._in_use.add(id(conn))
                        self._last_used[id(conn)] = time.monotonic()
                        return conn

                if len(self._pool) < self._max_connections:
                    try:
                        conn = self._create_connection()
                        self._pool.append(conn)
                        self._in_use.add(id(conn))
                        self._last_used[id(conn)] = time.monotonic()
                        return conn
                    except Exception as exc:
                        raise RuntimeError(f"Failed to create connection: {exc}") from exc

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Could not acquire a connection within {self._connection_timeout}s"
                    )
                self._condition.wait(timeout=min(remaining, 1.0))

    def release(self, conn: psycopg2.extensions.connection) -> None:
        with self._condition:
            self._in_use.discard(id(conn))
            self._last_used[id(conn)] = time.monotonic()
            self._condition.notify_all()

    def close_all(self) -> None:
        self._closed = True
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()
            self._in_use.clear()
            self._last_used.clear()

    @contextmanager
    def get_connection(self):
        conn = self.acquire()
        try:
            yield PatchedConnection(conn)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            self.release(conn)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total": len(self._pool),
                "in_use": len(self._in_use),
                "available": len(self._pool) - len(self._in_use),
                "max": self._max_connections,
            }


class PatchedCursor:
    """Cursor wrapper que valida SQL nativo PostgreSQL antes de executar."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, sql: str, params: Any = None) -> Any:
        sql = _normalize_sql_for_postgres(sql)
        if params is not None:
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def executemany(self, sql: str, seq_of_params: Any) -> Any:
        sql = _normalize_sql_for_postgres(sql)
        return self._cursor.executemany(sql, seq_of_params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._cursor.close()


class PatchedConnection:
    """Conexão wrapper que injeta PatchedCursor em cada chamada cursor()."""

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self._conn = conn

    def cursor(self, *args: Any, **kwargs: Any) -> PatchedCursor:
        return PatchedCursor(self._conn.cursor(*args, **kwargs))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()


_pool_instance: ConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = ConnectionPool(
                    database_url=DATABASE_URL,
                    min_connections=2,
                    max_connections=10,
                )
    return _pool_instance


def reset_pool() -> None:
    """Fecha e descarta o pool atual (usado em testes ou re-inicialização)."""
    global _pool_instance
    with _pool_lock:
        if _pool_instance is not None:
            try:
                _pool_instance.close_all()
            except Exception:
                pass
            _pool_instance = None
