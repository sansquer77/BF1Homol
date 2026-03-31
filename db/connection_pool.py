"""Pool de conexões PostgreSQL com adaptador de compatibilidade de cursor."""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Iterator, Optional

try:
    import streamlit as st
except Exception:  # no cover - fallback para execução fora do Streamlit
    st = None

import psycopg
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool as PsycopgConnectionPool

from db.db_config import (
    DATABASE_URL,
    DB_CONN_MAX_LIFETIME,
    DB_MAX_CONN,
    DB_MIN_CONN,
    DB_TIMEOUT,
)


class CompatRow(dict):
    """Linha de resultado compatível com acesso por índice e por nome."""

    def __init__(self, columns: list[str], values: list[Any]) -> None:
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _convert_placeholders(sql: str) -> str:
    """Converte placeholders qmark (?) para format (%s), ignorando strings."""
    result: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            result.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            result.append(ch)
        elif ch == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _parse_single_quoted_identifier(sql: str) -> Optional[str]:
    match = re.search(r"\((['\"])([^'\"]+)\1\)", sql)
    if not match:
        return None
    return match.group(2)


def _rewrite_sql_for_postgres(sql: str) -> tuple[str, bool]:
    """Reescreve SQL para compatibilidade com psycopg."""
    sql = re.sub(r"BOOLEAN\s+DEFAULT\s+0", "BOOLEAN DEFAULT FALSE", sql, flags=re.IGNORECASE)
    sql = re.sub(r"BOOLEAN\s+DEFAULT\s+1", "BOOLEAN DEFAULT TRUE", sql, flags=re.IGNORECASE)

    insert_or_replace = re.search(
        r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*VALUES\s*\((.+)\)\s*$",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if insert_or_replace:
        table_name = insert_or_replace.group(1)
        columns = [c.strip() for c in insert_or_replace.group(2).split(",")]
        values = insert_or_replace.group(3).strip()
        conflict_col = columns[0]
        updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns[1:])
        sql = (
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values}) "
            f"ON CONFLICT ({conflict_col}) DO UPDATE SET {updates}"
        )

    sql = _convert_placeholders(sql)
    return sql, False


def _insert_explicitly_sets_id(sql: str) -> bool:
    """Detecta INSERT com coluna id explícita no target list."""
    match = re.search(
        r"^\s*INSERT\s+INTO\s+[^\(]+\(([^\)]+)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return False
    raw_cols = match.group(1)
    cols = [c.strip().strip('"').lower() for c in raw_cols.split(",") if c.strip()]
    return "id" in cols


class PostgresCursorAdapter:
    """Cursor compatível com API sqlite para reduzir mudanças de código."""

    def __init__(self, cursor: psycopg.Cursor[Any]) -> None:
        self._cursor = cursor
        self._last_columns: list[str] = []
        self._lastrowid: Optional[int] = None

    @property
    def lastrowid(self) -> Optional[int]:
        return self._lastrowid

    @property
    def description(self) -> Optional[list[tuple[Any, ...]]]:
        if not self._cursor.description:
            return None
        # Compatibilidade com consumidores DB-API (ex.: pandas)
        return [(desc.name, None, None, None, None, None, None) for desc in self._cursor.description]

    def execute(self, sql: str, params: Optional[tuple[Any, ...] | list[Any]] = None) -> "PostgresCursorAdapter":
        rewritten_sql, requires_special_param = _rewrite_sql_for_postgres(sql)
        query_params: tuple[Any, ...] | list[Any] | None = params
        self._lastrowid = None

        if requires_special_param:
            identifier = _parse_single_quoted_identifier(sql)
            query_params = (identifier,) if identifier else ()

        self._cursor.execute(rewritten_sql, query_params)
        self._last_columns = [desc.name for desc in self._cursor.description] if self._cursor.description else []

        normalized = " ".join(rewritten_sql.strip().split()).lower()
        if (
            normalized.startswith("insert")
            and " returning " not in normalized
            and not _insert_explicitly_sets_id(rewritten_sql)
        ):
            try:
                self._cursor.execute("SAVEPOINT bf1_lastval_sp")
                self._cursor.execute("SELECT LASTVAL()")
                result = self._cursor.fetchone()
                if result:
                    self._lastrowid = int(result[0])
                self._cursor.execute("RELEASE SAVEPOINT bf1_lastval_sp")
            except Exception:
                try:
                    self._cursor.execute("ROLLBACK TO SAVEPOINT bf1_lastval_sp")
                    self._cursor.execute("RELEASE SAVEPOINT bf1_lastval_sp")
                except Exception:
                    pass
                self._lastrowid = None

        return self

    def executemany(
        self,
        sql: str,
        params_seq: list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...],
    ) -> "PostgresCursorAdapter":
        rewritten_sql, _ = _rewrite_sql_for_postgres(sql)
        self._lastrowid = None
        self._cursor.executemany(rewritten_sql, params_seq)
        self._last_columns = [desc.name for desc in self._cursor.description] if self._cursor.description else []
        return self

    def fetchone(self) -> Optional[CompatRow]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return CompatRow(self._last_columns, list(row))

    def fetchall(self) -> list[CompatRow]:
        rows = self._cursor.fetchall()
        return [CompatRow(self._last_columns, list(row)) for row in rows]

    def __getattr__(self, item: str) -> Any:
        return getattr(self._cursor, item)


class PostgresConnectionAdapter:
    """Conexão compatível com API sqlite para uso legado."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def cursor(self) -> PostgresCursorAdapter:
        return PostgresCursorAdapter(self._conn.cursor(row_factory=tuple_row))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PostgresConnectionAdapter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()

    def __getattr__(self, item: str) -> Any:
        return getattr(self._conn, item)

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
            kwargs={"autocommit": False},
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
            yield PostgresConnectionAdapter(conn)

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
