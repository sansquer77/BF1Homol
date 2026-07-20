"""Fachada de dados de provas/pilotos/resultados para a camada de UI."""

from utils.performance import instrumented_cache_data
from utils.dataframe_contracts import (
    PILOTOS_COLUMNS,
    PROVAS_COLUMNS,
    RESULTADOS_COLUMNS,
    with_required_columns,
)

from db.circuitos_utils import (
    atualizar_base_circuitos,
    get_circuitos_df as _repo_get_circuitos_df,
    get_temporadas_existentes_provas as _repo_get_temporadas_existentes_provas,
)
from db.repo_races import (
    get_pilotos_df as _repo_get_pilotos_df,
    get_provas_df as _repo_get_provas_df,
    get_resultados_df as _repo_get_resultados_df,
    get_resultados_usuario_df as _repo_get_resultados_usuario_df,
)


@instrumented_cache_data(ttl=60)
def get_pilotos_df():
    return with_required_columns(_repo_get_pilotos_df(), PILOTOS_COLUMNS)


@instrumented_cache_data(ttl=60)
def get_provas_df(temporada=None):
    return with_required_columns(_repo_get_provas_df(temporada), PROVAS_COLUMNS)


@instrumented_cache_data(ttl=60)
def get_resultados_df(temporada=None):
    return with_required_columns(_repo_get_resultados_df(temporada), RESULTADOS_COLUMNS)


@instrumented_cache_data(ttl=60)
def get_resultados_usuario_df(usuario_id: int, limit: int = 5000):
    return with_required_columns(_repo_get_resultados_usuario_df(usuario_id, limit), RESULTADOS_COLUMNS)


@instrumented_cache_data(ttl=300)
def get_circuitos_df():
    return _repo_get_circuitos_df()


@instrumented_cache_data(ttl=60)
def get_temporadas_existentes_provas():
    return _repo_get_temporadas_existentes_provas()

__all__ = [
    "atualizar_base_circuitos",
    "get_circuitos_df",
    "get_temporadas_existentes_provas",
    "get_pilotos_df",
    "get_provas_df",
    "get_resultados_df",
    "get_resultados_usuario_df",
]
