"""Repositório focado em apostas e classificação.

Mantém compatibilidade delegando para db.db_utils.
"""

from db.db_utils import (
    get_apostas_df,
    get_participantes_temporada_df,
    get_posicoes_participantes_df,
)

__all__ = [
    "get_apostas_df",
    "get_posicoes_participantes_df",
    "get_participantes_temporada_df",
]
