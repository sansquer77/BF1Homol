"""Fachada de dados de apostas/classificacao para a camada de UI."""

from db.repo_bets import (
    get_apostas_df,
    get_participantes_temporada_df,
    get_posicoes_participantes_df,
)

__all__ = [
    "get_apostas_df",
    "get_participantes_temporada_df",
    "get_posicoes_participantes_df",
]
