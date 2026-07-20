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


def get_aposta(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> dict | None:
    """Relê uma aposta diretamente do banco, sem cache, para confirmar escrita."""
    with db_connect() as conn:
        cols = get_table_columns(conn, "apostas")
        cur = conn.cursor()
        if temporada is not None and "temporada" in cols:
            cur.execute(
                "SELECT * FROM apostas WHERE usuario_id=%s AND prova_id=%s AND temporada=%s ORDER BY id DESC LIMIT 1",
                (int(usuario_id), int(prova_id), str(temporada)),
            )
        else:
            cur.execute(
                "SELECT * FROM apostas WHERE usuario_id=%s AND prova_id=%s ORDER BY id DESC LIMIT 1",
                (int(usuario_id), int(prova_id)),
            )
        row = cur.fetchone()
        cur.close()
    return dict(row) if row else None


def get_apostas_usuario_df(usuario_id: int, limit: int = 5000) -> pd.DataFrame:
    return _query_to_df(
        "SELECT * FROM apostas WHERE usuario_id = %s ORDER BY temporada, prova_id LIMIT %s",
        (int(usuario_id), max(1, min(int(limit), 5000))),
    )


def get_posicoes_participantes_df(temporada: Optional[str] = None) -> pd.DataFrame:
    if temporada:
        return _query_to_df(
            "SELECT * FROM posicoes_participantes WHERE temporada = %s ORDER BY prova_id, posicao",
            (temporada,),
        )
    return _query_to_df("SELECT * FROM posicoes_participantes ORDER BY prova_id, posicao")


def get_posicoes_usuario_df(usuario_id: int, limit: int = 5000) -> pd.DataFrame:
    return _query_to_df(
        "SELECT * FROM posicoes_participantes WHERE usuario_id = %s ORDER BY temporada, prova_id LIMIT %s",
        (int(usuario_id), max(1, min(int(limit), 5000))),
    )


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
    "get_apostas_usuario_df",
    "get_posicoes_participantes_df",
    "get_posicoes_usuario_df",
    "get_participantes_temporada_df",
]
