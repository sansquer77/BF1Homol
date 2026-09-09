"""Calendário autenticado da temporada."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import AdminParticipant, RaceResponse
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/seasons", response_model=list[str])
def seasons(context: AuthenticatedContext = Depends(get_current_context)) -> list[str]:
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT temporada FROM temporadas UNION SELECT DISTINCT temporada FROM provas WHERE temporada IS NOT NULL")
        values = sorted({str(row["temporada"]) for row in (cursor.fetchall() or []) if str(row.get("temporada") or "").isdigit()}, reverse=True)
    if context.perfil not in {"master", "admin"}:
        values = [value for value in values if value in context.temporadas_autorizadas]
    return values


def _iso_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


@router.get("", response_model=list[RaceResponse])
def calendar(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> list[RaceResponse]:
    authorize_season_object(season, context)
    from db.repo_races import get_provas_df

    frame = get_provas_df(season)
    races: list[RaceResponse] = []
    for row in frame.to_dict("records"):
        race_date = row.get("data")
        if race_date is None or str(race_date).strip() in {"", "NaT", "None"}:
            continue
        raw_time = row.get("horario_prova")
        race_time = str(raw_time)[:5] if raw_time is not None and str(raw_time).strip() else None
        races.append(RaceResponse(
            id=int(row.get("id") or 0),
            name=str(row.get("nome") or "Prova"),
            date=_iso_date(race_date),
            time=race_time,
            type=str(row.get("tipo") or "Normal"),
            status=str(row.get("status") or "Ativa"),
            season=str(row.get("temporada") or season),
            circuit_id=str(row["circuit_id"]) if row.get("circuit_id") else None,
        ))
    return races


@router.get("/participants", response_model=list[AdminParticipant])
def participants(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> list[AdminParticipant]:
    """Opções autorizadas para filtros; nunca concede acesso por id recebido do cliente."""
    authorize_season_object(season, context)
    from db.repo_bets import get_participantes_temporada_df

    frame = get_participantes_temporada_df(season)
    result: list[AdminParticipant] = []
    for row in frame.to_dict("records"):
        try:
            user_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if context.perfil in {"participante", "inativo"} and user_id != context.user_id:
            continue
        if str(row.get("perfil") or "").lower() == "master":
            continue
        result.append(AdminParticipant(id=user_id, name=str(row.get("nome") or "Participante")))
    return sorted(result, key=lambda item: item.name.casefold())
