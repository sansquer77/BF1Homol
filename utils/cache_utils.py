"""Utilitários leves para cache de dados Streamlit."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def clear_data_cache() -> None:
    """Limpa caches de leitura quando uma escrita altera dados de negócio."""
    try:
        import streamlit as st

        st.cache_data.clear()
    except Exception as exc:
        logger.debug("Falha ao limpar cache de dados: %s", exc)

