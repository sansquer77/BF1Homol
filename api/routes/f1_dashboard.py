"""Dashboard de estatísticas oficiais da Fórmula 1."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_context
from api.schemas import F1DashboardResponse
from services.access_control import AuthenticatedContext
from services.f1_dashboard_service import build_f1_dashboard

router = APIRouter(prefix="/f1-dashboard", tags=["f1-dashboard"])


@router.get("", response_model=F1DashboardResponse)
def f1_dashboard(
    season: int = Query(ge=1950, le=datetime.now().year),
    _: AuthenticatedContext = Depends(get_current_context),
) -> F1DashboardResponse:
    return F1DashboardResponse.model_validate(build_f1_dashboard(str(season)))
