"""Formulário e envio autenticado de apostas por prova."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import RaceBetRequest, RaceBetResponse, RaceBetSnapshot
from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.race_bets_v4_service import build_race_bet_snapshot, place_race_bet

router = APIRouter(prefix="/race-bets", tags=["race-bets"])


@router.get("", response_model=RaceBetSnapshot)
def race_bet_snapshot(
    season: str = Query(pattern=r"^\d{4}$"),
    race_id: int | None = Query(default=None, gt=0),
    context: AuthenticatedContext = Depends(get_current_context),
) -> RaceBetSnapshot:
    authorize_season_object(season, context)
    try:
        return RaceBetSnapshot.model_validate(build_race_bet_snapshot(season, context, race_id))
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("", response_model=RaceBetResponse)
def submit_race_bet(
    payload: RaceBetRequest,
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> RaceBetResponse:
    authorize_season_object(season, context)
    try:
        return RaceBetResponse.model_validate(place_race_bet(season, payload.race_id, [item.model_dump() for item in payload.allocations], payload.eleventh_driver, context))
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
