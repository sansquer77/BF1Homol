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

import logging

logger = logging.getLogger(__name__)


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
    """Converte placeholders qmark (?) para format (%s), ignorando literais de string.

    Mantido para compatibilidade com código legado que usa '?' como placeholder.
    Novo código deve usar '%s' diretamente (padrão psycopg/PostgreSQL).
    """
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


def _normalize_sql_for_postgres(sql: str) -> str:
    """Normaliza SQL legado mínimo para compatibilidade com psycopg.

    Diferente da versão anterior baseada em regex complexo, esta função aplica
    apenas transformações seguras e bem-definidas:
      1. Conversão de placeholders '?' → '%s' (via parser de string literal).
      2. Rejeita qualquer construção SQLite-exclusiva (INSERT OR REPLACE) com
         erro explícito, forçando o chamador a usar SQL nativo PostgreSQL.

    Todo SQL novo deve ser escrito diretamente em PostgreSQL — esta função
    existe apenas como camada de compatibilidade com código legado.
    """
    normalized = " ".join(sql.strip().split()).upper()

    # INSERT OR REPLACE não existe no PostgreSQL — deve ser substituído por
    # INSERT ... ON CONFLICT DO UPDATE pelo chamador.
    if re.match(r"^\s*INSERT\s+OR\s+REPLACE\s+", sql, re.IGNORECASE):
        raise ValueError(
            "INSERT OR REPLACE não é suportado no PostgreSQL. "
            "Use INSERT ... ON CONFLICT ({col}) DO UPDATE SET ... no lugar."
        )

    return _convert_placeholders(sql)


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
    """Cursor compatível com API sqlite3 para reduzir mudanças de código legado.

    Política de SQL:
    - Código novo deve usar SQL nativo PostgreSQL com %s como placeholder.
    - Código legado com '?' é convertido automaticamente por _normalize_sql_for_postgres.
    - INSERT OR REPLACE deve ser migrado para INSERT ... ON CONFLICT DO UPDATE.
    """

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
        normalized_sql = _normalize_sql_for_postgres(sql)
        self._lastrowid = None

        self._cursor.execute(normalized_sql, params)
        self._last_columns = [desc.name for desc in self._cursor.description] if self._cursor.description else []

        normalized_lower = " ".join(normalized_sql.strip().split()).lower()
        if (
            normalized_lower.startswith("insert")
            and " returning " not in normalized_lower
            and not _insert_explicitly_sets_id(normalized_sql)
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
        normalized_sql = _normalize_sql_for_postgres(sql)
        self._lastrowid = None
        self._cursor.executemany(normalized_sql, params_seq)
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
    """Conexão compatível com API sqlite3 para uso legado."""

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
