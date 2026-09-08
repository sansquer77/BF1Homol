"""Conteúdo institucional e metadados da versão 4."""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_context
from api.schemas import AboutResponse
from api.version import API_VERSION
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/about", response_model=AboutResponse)
def about(
    _: AuthenticatedContext = Depends(get_current_context),
) -> AboutResponse:
    return AboutResponse(
        name="BF1",
        full_name="Bolão de Fórmula 1",
        version=API_VERSION,
        architecture="Next.js + FastAPI + PostgreSQL",
    )
