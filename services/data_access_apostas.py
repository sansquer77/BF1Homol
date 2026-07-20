"""Fachada de dados de apostas/classificacao para a camada de UI."""

import streamlit as st

from db.repo_bets import (
    get_apostas_df as _repo_get_apostas_df,
    get_participantes_temporada_df as _repo_get_participantes_temporada_df,
    get_posicoes_participantes_df as _repo_get_posicoes_participantes_df,
)


@st.cache_data(ttl=60, show_spinner=False)
def get_apostas_df(temporada=None):
    return _repo_get_apostas_df(temporada)


@st.cache_data(ttl=60, show_spinner=False)
def get_posicoes_participantes_df(temporada=None):
    return _repo_get_posicoes_participantes_df(temporada)


@st.cache_data(ttl=60, show_spinner=False)
def get_participantes_temporada_df(temporada=None):
    return _repo_get_participantes_temporada_df(temporada)


__all__ = [
    "get_apostas_df",
    "get_participantes_temporada_df",
    "get_posicoes_participantes_df",
]
