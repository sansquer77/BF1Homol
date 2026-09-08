"""Análise autenticada das apostas da temporada."""

from fastapi import APIRouter, Depends, Query

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import BetsAnalysisResponse
from services.access_control import AuthenticatedContext
from services.bets_analysis_service import build_bets_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/bets", response_model=BetsAnalysisResponse)
def bets_analysis(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> BetsAnalysisResponse:
    authorize_season_object(season, context)
    scope_user_id = context.user_id if context.perfil in {"participante", "inativo"} else None
    return BetsAnalysisResponse.model_validate(build_bets_analysis(season, scope_user_id=scope_user_id))
