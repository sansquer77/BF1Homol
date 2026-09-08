"""Consulta autenticada do Hall da Fama."""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_context
from api.schemas import HallOfFameResponse
from services.access_control import AuthenticatedContext
from services.hall_read_service import build_hall_of_fame

router = APIRouter(prefix="/hall-of-fame", tags=["hall-of-fame"])


@router.get("", response_model=HallOfFameResponse)
def hall_of_fame(_: AuthenticatedContext = Depends(get_current_context)) -> HallOfFameResponse:
    return HallOfFameResponse.model_validate(build_hall_of_fame())
