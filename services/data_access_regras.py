"""Fachada de dados de regras para a camada de UI."""

from db.rules_utils import (
    associar_regra_temporada as _associar_regra_temporada,
    atualizar_regra as _atualizar_regra,
    clonar_regra as _clonar_regra,
    criar_regra as _criar_regra,
    excluir_regra as _excluir_regra,
    get_regra_by_id,
    get_regra_temporada,
    listar_regras,
    listar_temporadas_por_regra,
)
from services.access_control import require_operation


def criar_regra(*args, **kwargs):
    require_operation("regra.write")
    return _criar_regra(*args, **kwargs)


def atualizar_regra(*args, **kwargs):
    require_operation("regra.write")
    return _atualizar_regra(*args, **kwargs)


def excluir_regra(*args, **kwargs):
    require_operation("regra.write")
    return _excluir_regra(*args, **kwargs)


def associar_regra_temporada(temporada, *args, **kwargs):
    require_operation("regra.write", season=str(temporada))
    return _associar_regra_temporada(temporada, *args, **kwargs)


def clonar_regra(*args, **kwargs):
    require_operation("regra.write")
    return _clonar_regra(*args, **kwargs)

__all__ = [
    "associar_regra_temporada",
    "atualizar_regra",
    "clonar_regra",
    "criar_regra",
    "excluir_regra",
    "get_regra_by_id",
    "get_regra_temporada",
    "listar_regras",
    "listar_temporadas_por_regra",
]
