"""Repositório focado em corridas (provas/resultados/pilotos).

Mantém compatibilidade delegando para db.db_utils.
"""

from db.db_utils import (
    add_piloto,
    add_prova,
    delete_piloto,
    delete_prova,
    get_horario_prova,
    get_pilotos_df,
    get_provas_df,
    get_resultados_df,
    salvar_resultado,
    update_piloto,
    update_prova,
)

__all__ = [
    "get_pilotos_df",
    "add_piloto",
    "update_piloto",
    "delete_piloto",
    "get_provas_df",
    "add_prova",
    "update_prova",
    "delete_prova",
    "get_horario_prova",
    "get_resultados_df",
    "salvar_resultado",
]
