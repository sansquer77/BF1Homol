"""Pool de conexões com suporte a SQLite e PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
import re
import sqlite3
import threading
from typing import Any, Iterator, Optional

try:
    import streamlit as st
except Exception:  # pragma: no cover - fallback para execução fora do Streamlit
    st = None

import psycopg
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool as PsycopgConnectionPool

from db.db_config import (
    DATABASE_URL,
    DB_BACKEND,
    DB_CONN_MAX_LIFETIME,
    DB_MAX_CONN,
    DB_MIN_CONN,
    DB_PATH,
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


def _parse_sqlite_master_table_filter(sql: str) -> Optional[str]:
    match = re.search(r"name\s*=\s*(['\"])([^'\"]+)\1", sql, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(2)


def _rewrite_sql_for_postgres(sql: str) -> tuple[str, bool]:
    """Reescreve SQL SQLite para PostgreSQL quando necessário."""
    normalized = " ".join(sql.strip().split()).lower()

    if normalized.startswith("pragma "):
        if normalized.startswith("pragma table_info"):
            table_name = _parse_single_quoted_identifier(sql)
            if table_name:
                return (
                    """
                    SELECT
                        (ordinal_position - 1) AS cid,
                        column_name AS name,
                        data_type AS type,
                        CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                        column_default AS dflt_value,
                        CASE WHEN EXISTS (
                            SELECT 1
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                              ON tc.constraint_name = kcu.constraint_name
                             AND tc.table_schema = kcu.table_schema
                           WHERE tc.table_name = c.table_name
                             AND tc.table_schema = c.table_schema
                             AND tc.constraint_type = 'PRIMARY KEY'
                             AND kcu.column_name = c.column_name
                        ) THEN 1 ELSE 0 END AS pk
                    FROM information_schema.columns c
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    True,
                )
        if normalized.startswith("pragma index_list"):
            table_name = _parse_single_quoted_identifier(sql)
            if table_name:
                return (
                    """
                    SELECT
                        row_number() OVER (ORDER BY i.relname) - 1 AS seq,
                        i.relname AS name,
                        CASE WHEN idx.indisunique THEN 1 ELSE 0 END AS "unique",
                        'c' AS origin,
                        0 AS partial
                    FROM pg_class t
                    JOIN pg_index idx ON t.oid = idx.indrelid
                    JOIN pg_class i ON i.oid = idx.indexrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = current_schema()
                      AND t.relname = %s
                    ORDER BY i.relname
                    """,
                    True,
                )
        if normalized.startswith("pragma index_info"):
            index_name = _parse_single_quoted_identifier(sql)
            if index_name:
                return (
                    """
                    SELECT
                        x.n - 1 AS seqno,
                        a.attnum - 1 AS cid,
                        a.attname AS name
                    FROM pg_class i
                    JOIN pg_index idx ON i.oid = idx.indexrelid
                    JOIN pg_class t ON t.oid = idx.indrelid
                    JOIN pg_namespace nsp ON nsp.oid = i.relnamespace
                    JOIN LATERAL unnest(idx.indkey) WITH ORDINALITY AS x(attnum, n) ON TRUE
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
                    WHERE nsp.nspname = current_schema()
                      AND i.relname = %s
                    ORDER BY seqno
                    """,
                    True,
                )
        return ("SELECT 1 WHERE FALSE", False)

    if "from sqlite_master" in normalized:
        table_name = _parse_sqlite_master_table_filter(sql)
        if table_name:
            return (
                "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = %s",
                True,
            )
        return (
            "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema()",
            False,
        )

    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"DEFAULT\s*\(datetime\('now'\)\)", "DEFAULT CURRENT_TIMESTAMP", sql, flags=re.IGNORECASE)
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
            if not identifier and "sqlite_master" in sql.lower():
                identifier = _parse_sqlite_master_table_filter(sql)
            query_params = (identifier,) if identifier else ()

        self._cursor.execute(rewritten_sql, query_params)
        self._last_columns = [desc.name for desc in self._cursor.description] if self._cursor.description else []

        normalized = " ".join(rewritten_sql.strip().split()).lower()
        if normalized.startswith("insert") and " returning " not in normalized:
            try:
                self._cursor.execute("SELECT LASTVAL()")
                result = self._cursor.fetchone()
                if result:
                    self._lastrowid = int(result[0])
            except Exception:
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
    """Pool de conexões thread-safe com fallback para SQLite."""

    def __init__(self, db_path: str, pool_size: int = 5, timeout: float = 30.0) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._connections: list = []
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(pool_size)
        self._pg_pool: Optional[PsycopgConnectionPool] = None
        self._backend = DB_BACKEND
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Inicializa recursos do backend selecionado."""
        if self._backend == "postgres":
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
            return

        with self._lock:
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._connections.append(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """Cria uma nova conexão com SQLite."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging para melhor concorrência
        conn.execute("PRAGMA synchronous=NORMAL")  # Menos lento que FULL, mais seguro que OFF
        conn.execute("PRAGMA cache_size=-64000")  # 64MB de cache
        return conn

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        """Retorna conexão do pool como context manager."""
        if self._backend == "postgres":
            if self._pg_pool is None:
                raise RuntimeError("Pool PostgreSQL não inicializado")
            with self._pg_pool.connection() as conn:
                yield PostgresConnectionAdapter(conn)
            return

        self._semaphore.acquire()
        conn = None
        try:
            with self._lock:
                if self._connections:
                    conn = self._connections.pop()
            
            if conn is None:
                conn = self._create_connection()
            
            yield conn
            
        finally:
            if conn:
                with self._lock:
                    if len(self._connections) < self.pool_size:
                        self._connections.append(conn)
                    else:
                        conn.close()
            self._semaphore.release()

    def close_all(self) -> None:
        """Fecha todas as conexões do pool."""
        if self._backend == "postgres" and self._pg_pool is not None:
            self._pg_pool.close()
            self._pg_pool = None
            return

        with self._lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()


# Instância global do pool
_pool: Optional[ConnectionPool] = None

def _build_pool(db_path: Optional[str], pool_size: int) -> ConnectionPool:
    target_path = db_path or str(DB_PATH)
    return ConnectionPool(target_path, pool_size, DB_TIMEOUT)


if st is not None:

    @st.cache_resource(show_spinner=False)
    def _get_cached_pool(db_path: Optional[str], pool_size: int) -> ConnectionPool:
        return _build_pool(db_path, pool_size)

else:

    def _get_cached_pool(db_path: Optional[str], pool_size: int) -> ConnectionPool:
        return _build_pool(db_path, pool_size)


def init_pool(db_path: Optional[str] = None, pool_size: int = 5) -> None:
    """Inicializa o pool global."""
    global _pool
    _pool = _get_cached_pool(db_path, pool_size)

def get_pool() -> ConnectionPool:
    """Retorna o pool global."""
    global _pool
    if _pool is None:
        init_pool(str(DB_PATH))
    return _pool

def close_pool() -> None:
    """Fecha o pool global."""
    global _pool
    if _pool:
        _pool.close_all()
        _pool = None
