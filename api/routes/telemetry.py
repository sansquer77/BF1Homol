"""Resumo autenticado da Telemetria V4."""

from fastapi import APIRouter, Depends, Query

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import PersonalBetsResponse, PersonalHistoryResponse, TelemetryResponse
from services.access_control import AuthenticatedContext
from services.telemetry_service import build_telemetry_snapshot

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/bets", response_model=PersonalBetsResponse)
def personal_bets(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)) -> PersonalBetsResponse:
    authorize_season_object(season, context)
    from services.participant_panel_v4_service import build_personal_bets
    return PersonalBetsResponse.model_validate(build_personal_bets(context.user_id, season))


@router.get("/history", response_model=PersonalHistoryResponse)
def personal_history(context: AuthenticatedContext = Depends(get_current_context)) -> PersonalHistoryResponse:
    from services.participant_panel_v4_service import build_personal_history
    return PersonalHistoryResponse.model_validate(build_personal_history(context.user_id))


@router.get("", response_model=TelemetryResponse)
def telemetry(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> TelemetryResponse:
    authorize_season_object(season, context)
    return TelemetryResponse.model_validate(
        build_telemetry_snapshot(context.user_id, context.nome, season)
    )
