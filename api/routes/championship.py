"""Contratos V4 para apostas e resultado do Campeonato."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import ChampionshipBetRecord, ChampionshipBetRequest, ChampionshipResponse, ChampionshipResult
from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.championship_v4_service import build_championship_snapshot, place_championship_bet, save_official_result

router = APIRouter(prefix="/championship", tags=["championship"])


@router.get("", response_model=ChampionshipResponse)
def championship_snapshot(season: int = Query(ge=2000, le=2100), context: AuthenticatedContext = Depends(get_current_context)) -> ChampionshipResponse:
    if context.perfil not in {"participante", "admin", "master"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    authorize_season_object(str(season), context)
    return ChampionshipResponse.model_validate(build_championship_snapshot(season, context))


@router.post("/bet", response_model=ChampionshipBetRecord, status_code=status.HTTP_200_OK)
def championship_bet(season: int = Query(ge=2000, le=2100), payload: ChampionshipBetRequest = ..., context: AuthenticatedContext = Depends(get_current_context)) -> ChampionshipBetRecord:
    authorize_season_object(str(season), context)
    try:
        return ChampionshipBetRecord.model_validate({"user_nome": context.nome, **place_championship_bet(season, payload.champion, payload.vice, payload.team, context)})
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/result", response_model=ChampionshipResult)
def championship_result(season: int = Query(ge=2000, le=2100), payload: ChampionshipBetRequest = ..., context: AuthenticatedContext = Depends(get_current_context)) -> ChampionshipResult:
    authorize_season_object(str(season), context)
    try:
        return ChampionshipResult.model_validate(save_official_result(season, payload.champion, payload.vice, payload.team, context))
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
