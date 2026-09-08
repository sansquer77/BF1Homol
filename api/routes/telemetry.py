"""Resumo autenticado da Telemetria V4."""

from fastapi import APIRouter, Depends, Query

from api.dependencies import authorize_season_object, get_current_context
from api.schemas import TelemetryResponse
from services.access_control import AuthenticatedContext
from services.telemetry_service import build_telemetry_snapshot

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("", response_model=TelemetryResponse)
def telemetry(
    season: str = Query(pattern=r"^\d{4}$"),
    context: AuthenticatedContext = Depends(get_current_context),
) -> TelemetryResponse:
    authorize_season_object(season, context)
    return TelemetryResponse.model_validate(
        build_telemetry_snapshot(context.user_id, context.nome, season)
    )
