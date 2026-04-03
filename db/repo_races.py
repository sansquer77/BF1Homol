"""Repositório focado em corridas (provas/resultados/pilotos)."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from db.db_schema import db_connect, get_table_columns

logger = logging.getLogger(__name__)

_COLUNAS_PILOTOS_VALIDAS: frozenset[str] = frozenset({"nome", "equipe", "status", "numero"})
_COLUNAS_PROVAS_VALIDAS: frozenset[str] = frozenset({"nome", "data", "horario_prova", "tipo", "status", "temporada"})


def _query_to_df(query: str, params: tuple | None = None) -> pd.DataFrame:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        rows = cur.fetchall() or []
        if not rows:
            col_names = [desc[0] for desc in (cur.description or [])]
            cur.close()
            return pd.DataFrame(columns=col_names)
        cur.close()
    return pd.DataFrame([dict(r) for r in rows])


def get_pilotos_df() -> pd.DataFrame:
    return _query_to_df("SELECT * FROM pilotos ORDER BY nome")


def get_provas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    if temporada:
        return _query_to_df(
            "SELECT * FROM provas WHERE temporada = %s OR temporada IS NULL ORDER BY data ASC, id ASC",
            (temporada,),
        )
    return _query_to_df("SELECT * FROM provas ORDER BY data ASC, id ASC")


def get_resultados_df(temporada: Optional[str] = None) -> pd.DataFrame:
    with db_connect() as conn:
        cols = get_table_columns(conn, "resultados")
        has_jsonb = "posicoes_jsonb" in cols
        has_abandono_arr = "abandono_arr" in cols

        extra = ""
        if has_jsonb:
            extra += ", posicoes_jsonb"
        if has_abandono_arr:
            extra += ", abandono_arr"

        cur = conn.cursor()
        if temporada:
            cur.execute(
                f"SELECT prova_id, posicoes, abandono_pilotos{extra} "
                "FROM resultados "
                "JOIN provas ON resultados.prova_id = provas.id "
                "WHERE provas.temporada = %s OR provas.temporada IS NULL",
                (temporada,),
            )
        else:
            cur.execute(f"SELECT prova_id, posicoes, abandono_pilotos{extra} FROM resultados")

        rows = cur.fetchall() or []
        if not rows:
            col_names = [desc[0] for desc in (cur.description or [])]
            cur.close()
            return pd.DataFrame(columns=col_names)
        cur.close()

    return pd.DataFrame([dict(r) for r in rows])


def add_piloto(nome: str, equipe: str = "", status: str = "Ativo", numero: int = 0) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO pilotos (nome, equipe, status, numero) VALUES (%s, %s, %s, %s)",
                (nome, equipe, status, numero),
            )
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("add_piloto falhou: %s", exc)
        return False


def update_piloto(piloto_id: int, **campos) -> bool:
    if not campos:
        return False
    campos_invalidos = set(campos) - _COLUNAS_PILOTOS_VALIDAS
    if campos_invalidos:
        logger.error("update_piloto: colunas não permitidas rejeitadas: %s", campos_invalidos)
        raise ValueError(f"Colunas não permitidas em update_piloto: {campos_invalidos}")
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [piloto_id]
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE pilotos SET {set_clause} WHERE id = %s", values)
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("update_piloto falhou: %s", exc)
        return False


def delete_piloto(piloto_id: int) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM pilotos WHERE id = %s", (piloto_id,))
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("delete_piloto falhou: %s", exc)
        return False


def add_prova(
    nome: str,
    data: str,
    horario_prova: str = "",
    tipo: str = "Normal",
    status: str = "Pendente",
    temporada: Optional[str] = None,
) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO provas (nome, data, horario_prova, tipo, status, temporada) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (nome, data, horario_prova, tipo, status, temporada),
            )
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("add_prova falhou: %s", exc)
        return False


def update_prova(prova_id: int, **campos) -> bool:
    if not campos:
        return False
    campos_invalidos = set(campos) - _COLUNAS_PROVAS_VALIDAS
    if campos_invalidos:
        logger.error("update_prova: colunas não permitidas rejeitadas: %s", campos_invalidos)
        raise ValueError(f"Colunas não permitidas em update_prova: {campos_invalidos}")
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [prova_id]
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE provas SET {set_clause} WHERE id = %s", values)
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("update_prova falhou: %s", exc)
        return False


def delete_prova(prova_id: int) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM provas WHERE id = %s", (prova_id,))
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("delete_prova falhou: %s", exc)
        return False


def get_horario_prova(prova_id: int) -> tuple[Optional[str], Optional[str], Optional[str]]:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nome, data, horario_prova FROM provas WHERE id = %s", (prova_id,))
        row = cur.fetchone()
        cur.close()
    if row:
        return row["nome"], row["data"], row["horario_prova"]
    return None, None, None


def salvar_resultado(prova_id: int, posicoes: str, abandono_pilotos: str = "") -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO resultados (prova_id, posicoes, abandono_pilotos)
                VALUES (%s, %s, %s)
                ON CONFLICT (prova_id) DO UPDATE
                    SET posicoes = EXCLUDED.posicoes,
                        abandono_pilotos = EXCLUDED.abandono_pilotos
                """,
                (prova_id, posicoes, abandono_pilotos),
            )
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("salvar_resultado falhou: %s", exc)
        return False

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
