"""Fachada de dados de backup/importacao para a camada de UI e utils."""

from db.backup_excel import download_tabela, upload_tabela as _upload_tabela
from db.backup_sql import create_next_temporada as _create_next_temporada, download_db, get_postgres_backup_mode, list_temporadas, upload_db as _upload_db
from services.access_control import require_operation


def upload_tabela(*args, **kwargs):
    require_operation("backup.write")
    return _upload_tabela(*args, **kwargs)


def upload_db(*args, **kwargs):
    require_operation("backup.write")
    return _upload_db(*args, **kwargs)


def create_next_temporada(*args, **kwargs):
    require_operation("backup.write")
    return _create_next_temporada(*args, **kwargs)

__all__ = [
    "download_tabela",
    "upload_tabela",
    "create_next_temporada",
    "download_db",
    "get_postgres_backup_mode",
    "list_temporadas",
    "upload_db",
]
