"""Operações de escrita de apostas.

Camada focada para persistência e geração de apostas.
Mantém compatibilidade delegando para services.bets_service.
"""

from services.bets_service import (
    ajustar_aposta_para_regras,
    gerar_aposta_aleatoria,
    gerar_aposta_aleatoria_com_regras,
    gerar_aposta_automatica,
    gerar_aposta_sem_ideias,
    salvar_aposta,
)

__all__ = [
    "salvar_aposta",
    "gerar_aposta_aleatoria",
    "gerar_aposta_aleatoria_com_regras",
    "ajustar_aposta_para_regras",
    "gerar_aposta_automatica",
    "gerar_aposta_sem_ideias",
]
