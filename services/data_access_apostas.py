"""Fachada de dados de apostas/classificacao para a camada de UI."""

from utils.performance import instrumented_cache_data
from utils.dataframe_contracts import APOSTAS_COLUMNS, with_required_columns

from db.repo_bets import (
    get_apostas_df as _repo_get_apostas_df,
    get_apostas_usuario_df as _repo_get_apostas_usuario_df,
    get_participantes_temporada_df as _repo_get_participantes_temporada_df,
    get_posicoes_participantes_df as _repo_get_posicoes_participantes_df,
    get_posicoes_usuario_df as _repo_get_posicoes_usuario_df,
)

@instrumented_cache_data(ttl=60)
def get_apostas_df(temporada=None):
    return with_required_columns(_repo_get_apostas_df(temporada), APOSTAS_COLUMNS)


@instrumented_cache_data(ttl=60)
def get_apostas_usuario_df(usuario_id: int, limit: int = 5000):
    return with_required_columns(_repo_get_apostas_usuario_df(usuario_id, limit), APOSTAS_COLUMNS)


@instrumented_cache_data(ttl=60)
def get_posicoes_participantes_df(temporada=None):
    return _repo_get_posicoes_participantes_df(temporada)


@instrumented_cache_data(ttl=60)
def get_posicoes_usuario_df(usuario_id: int, limit: int = 5000):
    return _repo_get_posicoes_usuario_df(usuario_id, limit)


@instrumented_cache_data(ttl=60)
def get_participantes_temporada_df(temporada=None):
    return _repo_get_participantes_temporada_df(temporada)


__all__ = [
    "get_apostas_df",
    "get_apostas_usuario_df",
    "get_participantes_temporada_df",
    "get_posicoes_participantes_df",
    "get_posicoes_usuario_df",
]
