"""Fachada de utilitarios de infraestrutura de dados para UI."""

from db.db_schema import db_connect, get_table_columns

__all__ = [
    "db_connect",
    "get_table_columns",
]
