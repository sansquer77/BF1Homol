"""Operações SQL de backup/restore.

Camada focada para dump/restore completo.
Mantém compatibilidade delegando para db.backup_utils.
"""

from db.backup_utils import (
    create_next_temporada,
    download_db,
    get_postgres_backup_mode,
    list_temporadas,
    restore_backup_from_sql,
    upload_db,
)

__all__ = [
    "list_temporadas",
    "create_next_temporada",
    "get_postgres_backup_mode",
    "download_db",
    "restore_backup_from_sql",
    "upload_db",
]
