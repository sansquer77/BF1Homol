"""Validações e ajustes de regras de apostas.

Camada focada para regras de negócio de aposta.
Mantém compatibilidade delegando para services.bets_service.
"""

from services.bets_service import (
    _aposta_valida_regras,
    ajustar_aposta_para_regras,
    pode_fazer_aposta,
)

__all__ = [
    "pode_fazer_aposta",
    "_aposta_valida_regras",
    "ajustar_aposta_para_regras",
]
