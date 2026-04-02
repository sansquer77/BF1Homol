"""Helpers de schema e inicialização.

Camada focada para init/schema/migrations, mantendo compatibilidade.
"""

from db.db_utils import db_connect, get_table_columns, init_db, table_exists
from db.migrations import run_migrations

__all__ = [
    "db_connect",
    "get_table_columns",
    "table_exists",
    "init_db",
    "run_migrations",
]
