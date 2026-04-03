"""Fachada de dados de regras para a camada de UI."""

from db.rules_utils import (
    associar_regra_temporada,
    atualizar_regra,
    clonar_regra,
    criar_regra,
    excluir_regra,
    get_regra_by_id,
    get_regra_temporada,
    listar_regras,
    listar_temporadas_por_regra,
)

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
