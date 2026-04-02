"""Repositório focado em logs de aposta e acesso.

Mantém compatibilidade delegando para db.db_utils.
"""

from db.db_utils import log_aposta_existe, registrar_log_aposta

__all__ = ["registrar_log_aposta", "log_aposta_existe"]
