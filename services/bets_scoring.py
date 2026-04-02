"""Cálculo de pontuação e classificação de apostas.

Camada focada para scoring/classificação.
Mantém compatibilidade delegando para services.bets_service.
"""

from services.bets_service import (
    _parse_datetime_sp,
    atualizar_classificacoes_todas_as_provas,
    calcular_pontuacao_lote,
    salvar_classificacao_prova,
)

__all__ = [
    "_parse_datetime_sp",
    "calcular_pontuacao_lote",
    "salvar_classificacao_prova",
    "atualizar_classificacoes_todas_as_provas",
]
