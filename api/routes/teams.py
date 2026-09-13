"""Paleta autenticada das equipes usada nas marcações visuais da V4."""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_context
from api.schemas import AdminTeam
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[AdminTeam])
def teams(_: AuthenticatedContext = Depends(get_current_context)) -> list[AdminTeam]:
    from db.equipes_utils import list_equipes

    return [
        AdminTeam(
            id=int(row["id"]),
            name=str(row["nome"]),
            primary_color=str(row.get("cor_primaria") or "#687284"),
            secondary_color=str(row["cor_secundaria"]) if row.get("cor_secundaria") else None,
            status=str(row.get("status") or "Ativa"),
        )
        for row in list_equipes()
    ]
