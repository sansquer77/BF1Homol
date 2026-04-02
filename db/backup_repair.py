"""Reparos de literais legados em restores.

Camada focada para corrigir JSON/ARRAY legados no fallback por statement.
Mantém compatibilidade delegando para db.backup_utils.
"""

from db.backup_utils import (
    _repair_insert_array_literals,
    _repair_insert_json_literals,
    _repair_insert_legacy_literals,
)

__all__ = [
    "_repair_insert_json_literals",
    "_repair_insert_array_literals",
    "_repair_insert_legacy_literals",
]
