"""Operações de backup por tabela em Excel.

Camada focada para download/upload de tabelas em planilha.
Mantém compatibilidade delegando para db.backup_utils.
"""

from db.backup_utils import download_tabela, upload_tabela

__all__ = ["download_tabela", "upload_tabela"]
