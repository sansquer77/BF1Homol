"""Casos de uso de manutenção do Hall da Fama na API V4.

Toda autoridade vem do contexto autenticado; o payload não escolhe perfil.
"""
from __future__ import annotations

from typing import Any

from services.access_control import AuthenticatedContext, authorize_context


def _db_connect():
    from db.db_schema import db_connect
    return db_connect()


def _clear_cache() -> None:
    from utils.cache_utils import clear_data_cache
    clear_data_cache("hall_da_fama", "classificacao", "historico")


def _master(context: AuthenticatedContext, season: str | None = None) -> None:
    authorize_context(context, frozenset({"master"}), season=season)


def _validate(season: str, position: int, points: float) -> tuple[str, int, float]:
    season = str(season).strip()
    if not season or len(season) != 4 or not season.isdigit():
        raise ValueError("Temporada inválida.")
    position = int(position)
    if position < 1 or position > 1000:
        raise ValueError("A posição deve estar entre 1 e 1000.")
    points = float(points)
    if points < 0:
        raise ValueError("A pontuação não pode ser negativa.")
    return season, position, points


def list_hall_admin(context: AuthenticatedContext, season: str | None = None) -> dict[str, Any]:
    _master(context, season)
    with _db_connect() as conn:
        cur = conn.cursor()
        params: tuple[Any, ...] = (season,) if season else ()
        where = "WHERE h.temporada = %s" if season else ""
        cur.execute(f"""SELECT h.id, h.usuario_id, u.nome, h.temporada, h.posicao_final, h.pontos
                        FROM hall_da_fama h JOIN usuarios u ON u.id = h.usuario_id
                        {where} ORDER BY h.temporada DESC, h.posicao_final ASC, h.id ASC""", params)
        records = [{"id": r[0], "user_id": r[1], "participant": r[2], "season": r[3], "position": r[4], "points": float(r[5] or 0)} for r in cur.fetchall()]
        cur.execute("SELECT id, nome FROM usuarios WHERE LOWER(COALESCE(status, 'ativo')) = 'ativo' ORDER BY nome")
        participants = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        cur.close()
    return {"records": records, "participants": participants}


def save_hall_record(context: AuthenticatedContext, *, user_id: int, season: str, position: int, points: float) -> None:
    _master(context, season)
    season, position, points = _validate(season, position, points)
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM usuarios WHERE id = %s", (int(user_id),))
        if cur.fetchone() is None:
            raise ValueError("Participante não encontrado.")
        cur.execute("""INSERT INTO hall_da_fama (usuario_id, temporada, posicao_final, pontos)
                     VALUES (%s, %s, %s, %s)
                     ON CONFLICT (usuario_id, temporada) DO UPDATE
                     SET posicao_final = EXCLUDED.posicao_final, pontos = EXCLUDED.pontos""",
                    (int(user_id), season, position, points))
        conn.commit()
        cur.close()
    _clear_cache()


def update_hall_record(context: AuthenticatedContext, record_id: int, *, season: str, position: int, points: float) -> None:
    _master(context, season)
    season, position, points = _validate(season, position, points)
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE hall_da_fama SET temporada=%s, posicao_final=%s, pontos=%s WHERE id=%s", (season, position, points, int(record_id)))
        if cur.rowcount != 1:
            raise ValueError("Registro do Hall da Fama não encontrado.")
        conn.commit()
        cur.close()
    _clear_cache()


def delete_hall_record(context: AuthenticatedContext, record_id: int) -> None:
    _master(context)
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM hall_da_fama WHERE id=%s", (int(record_id),))
        if cur.rowcount != 1:
            raise ValueError("Registro do Hall da Fama não encontrado.")
        conn.commit()
        cur.close()
    _clear_cache()


def bulk_save_hall(context: AuthenticatedContext, records: list[dict[str, Any]]) -> int:
    _master(context)
    if not records or len(records) > 500:
        raise ValueError("O lote deve conter entre 1 e 500 registros.")
    prepared = []
    for item in records:
        season, position, points = _validate(item.get("season", ""), item.get("position", 0), item.get("points", 0))
        prepared.append((int(item.get("user_id", 0)), season, position, points))
    with _db_connect() as conn:
        cur = conn.cursor()
        for user_id, season, position, points in prepared:
            cur.execute("SELECT 1 FROM usuarios WHERE id=%s", (user_id,))
            if cur.fetchone() is None:
                raise ValueError(f"Participante {user_id} não encontrado.")
            cur.execute("""INSERT INTO hall_da_fama (usuario_id, temporada, posicao_final, pontos) VALUES (%s,%s,%s,%s)
                         ON CONFLICT (usuario_id, temporada) DO UPDATE SET posicao_final=EXCLUDED.posicao_final,pontos=EXCLUDED.pontos""", (user_id, season, position, points))
        conn.commit()
        cur.close()
    _clear_cache()
    return len(prepared)
