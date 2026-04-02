"""Validações de integridade para backup/import.

Camada focada para validações de FK e colunas obrigatórias.
Mantém compatibilidade delegando para db.backup_utils.
"""

from db.backup_utils import (
    _get_required_columns_for_insert,
    _get_table_column_types,
    _prevalidate_fk_values,
    _table_columns,
)

__all__ = [
    "_table_columns",
    "_get_table_column_types",
    "_get_required_columns_for_insert",
    "_prevalidate_fk_values",
]
