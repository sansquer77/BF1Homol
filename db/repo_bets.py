"""Repositório focado em apostas e classificação."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from db.db_schema import db_connect, get_table_columns, table_exists


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


def get_apostas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    if temporada:
        return _query_to_df("SELECT * FROM apostas WHERE temporada = %s", (temporada,))
    return _query_to_df("SELECT * FROM apostas")


def get_posicoes_participantes_df(temporada: Optional[str] = None) -> pd.DataFrame:
    if temporada:
        return _query_to_df(
            "SELECT * FROM posicoes_participantes WHERE temporada = %s ORDER BY prova_id, posicao",
            (temporada,),
        )
    return _query_to_df("SELECT * FROM posicoes_participantes ORDER BY prova_id, posicao")


def _usuarios_status_historico_exists(conn) -> bool:
    return table_exists(conn, "usuarios_status_historico")


def get_participantes_temporada_df(temporada: Optional[str] = None) -> pd.DataFrame:
    if temporada is None:
        temporada = str(datetime.now().year)
    season_start = f"{temporada}-01-01 00:00:00"
    season_end = f"{temporada}-12-31 23:59:59"

    with db_connect() as conn:
        has_hist = _usuarios_status_historico_exists(conn)
        if not has_hist:
            return _query_to_df("SELECT * FROM usuarios WHERE lower(trim(coalesce(status,''))) = 'ativo'")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM usuarios_status_historico")
        row = cur.fetchone()
        cur.close()
        if not row or int(row["cnt"]) == 0:
            return _query_to_df("SELECT * FROM usuarios WHERE lower(trim(coalesce(status,''))) = 'ativo'")

    df = _query_to_df(
        """
        SELECT DISTINCT u.*
        FROM usuarios u
        JOIN usuarios_status_historico h ON h.usuario_id = u.id
        WHERE lower(trim(coalesce(h.status,''))) = 'ativo'
          AND h.inicio_em <= %s
          AND (h.fim_em IS NULL OR h.fim_em >= %s)
        """,
        (season_end, season_start),
    )
    if not df.empty:
        return df
    return _query_to_df("SELECT * FROM usuarios WHERE lower(trim(coalesce(status,''))) = 'ativo'")

__all__ = [
    "get_apostas_df",
    "get_posicoes_participantes_df",
    "get_participantes_temporada_df",
]
