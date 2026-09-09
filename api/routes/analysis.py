"""Análise autenticada das apostas da temporada."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import BetsAnalysisResponse
from services.access_control import AuthenticatedContext
from services.bets_analysis_service import build_bets_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/bets", response_model=BetsAnalysisResponse)
def bets_analysis(
    season: str = Query(pattern=r"^\d{4}$"),
    participant_id: int | None = Query(default=None, gt=0),
    context: AuthenticatedContext = Depends(get_current_context),
) -> BetsAnalysisResponse:
    authorize_season_object(season, context)
    restricted = context.perfil in {"participante", "inativo"}
    if restricted and participant_id is not None and participant_id != context.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")
    scope_user_id = context.user_id if restricted else participant_id
    if participant_id is not None and not restricted:
        from db.repo_bets import get_participantes_temporada_df
        frame = get_participantes_temporada_df(season)
        allowed: set[int] = set()
        for value in frame.get("id", []):
            try:
                allowed.add(int(value))
            except (TypeError, ValueError):
                continue
        if participant_id not in allowed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")
    return BetsAnalysisResponse.model_validate(build_bets_analysis(season, scope_user_id=scope_user_id, include_participants=not restricted))
