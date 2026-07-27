"""Allow pure service tests to import the DB layer when psycopg is not installed."""

from __future__ import annotations

import importlib.util
import os
import sys
import types


def install_if_needed() -> None:
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/bf1_test")
    if "psycopg" in sys.modules or importlib.util.find_spec("psycopg") is not None:
        return
    psycopg = types.ModuleType("psycopg")
    rows = types.ModuleType("psycopg.rows")
    rows.dict_row = object()
    pool = types.ModuleType("psycopg_pool")

    class UnavailableConnectionPool:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("psycopg não está instalado neste ambiente de testes.")

    pool.ConnectionPool = UnavailableConnectionPool
    psycopg.rows = rows
    sys.modules.setdefault("psycopg", psycopg)
    sys.modules.setdefault("psycopg.rows", rows)
    sys.modules.setdefault("psycopg_pool", pool)
