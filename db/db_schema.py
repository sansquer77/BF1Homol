"""Helpers de schema e inicialização."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from db.connection_pool import get_pool
from db.migrations import run_migrations

logger = logging.getLogger(__name__)


@contextmanager
def db_connect():
    pool = get_pool()
    with pool.get_connection() as conn:
        yield conn


def get_table_columns(conn, table_name: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    cols = [row["column_name"] for row in cur.fetchall()]
    cur.close()
    return cols


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def init_db() -> None:
    from db.db_utils import init_db as _init_db

    _init_db()

__all__ = [
    "db_connect",
    "get_table_columns",
    "table_exists",
    "init_db",
    "run_migrations",
]
