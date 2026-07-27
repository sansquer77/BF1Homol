"""Utilitários leves para cache de dados."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def clear_data_cache(*tags: str) -> None:
    """Limpa caches de leitura quando uma escrita altera dados de negócio."""
    try:
        from utils.ttl_cache import clear_all_caches
        clear_all_caches(*tags)
    except Exception as exc:
        logger.debug("Falha ao limpar cache de dados: %s", exc)
