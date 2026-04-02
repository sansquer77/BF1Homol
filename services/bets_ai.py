"""Recursos de IA/contexto para geração automática de apostas.

Camada focada para integrações e parsing de payload de IA.
Mantém compatibilidade delegando para services.bets_service.
"""

from services.bets_service import (
    _extrair_json_texto,
    _gerar_aposta_perplexity,
    _get_contexto_temporada_atual_ergast,
)

__all__ = [
    "_extrair_json_texto",
    "_get_contexto_temporada_atual_ergast",
    "_gerar_aposta_perplexity",
]
