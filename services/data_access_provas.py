"""Fachada de dados de provas/pilotos/resultados para a camada de UI."""

import streamlit as st

from db.circuitos_utils import (
    atualizar_base_circuitos,
    get_circuitos_df as _repo_get_circuitos_df,
    get_temporadas_existentes_provas as _repo_get_temporadas_existentes_provas,
)
from db.repo_races import (
    get_pilotos_df as _repo_get_pilotos_df,
    get_provas_df as _repo_get_provas_df,
    get_resultados_df as _repo_get_resultados_df,
)


@st.cache_data(ttl=60, show_spinner=False)
def get_pilotos_df():
    return _repo_get_pilotos_df()


@st.cache_data(ttl=60, show_spinner=False)
def get_provas_df(temporada=None):
    return _repo_get_provas_df(temporada)


@st.cache_data(ttl=60, show_spinner=False)
def get_resultados_df(temporada=None):
    return _repo_get_resultados_df(temporada)


@st.cache_data(ttl=300, show_spinner=False)
def get_circuitos_df():
    return _repo_get_circuitos_df()


@st.cache_data(ttl=60, show_spinner=False)
def get_temporadas_existentes_provas():
    return _repo_get_temporadas_existentes_provas()

__all__ = [
    "atualizar_base_circuitos",
    "get_circuitos_df",
    "get_temporadas_existentes_provas",
    "get_pilotos_df",
    "get_provas_df",
    "get_resultados_df",
]
