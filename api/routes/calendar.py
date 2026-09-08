"""Calendário autenticado da temporada."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import RaceResponse
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/calendar", tags=["calendar"])


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
