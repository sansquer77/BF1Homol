"""Contrato inicial de identidade; gestão completa pertence à Fase 7."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import authorize_user_object, get_current_context
from api.schemas import UserResponse
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, context: AuthenticatedContext = Depends(get_current_context)) -> UserResponse:
    authorize_user_object(user_id, context)
    from db.repo_users import get_user_by_id
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")
    return UserResponse(
        id=int(user["id"]), nome=str(user.get("nome") or ""), email=str(user.get("email") or ""),
        perfil=str(user.get("perfil") or "participante").lower(), status=str(user.get("status") or "").lower(),
        must_change_password=bool(user.get("must_change_password") or False),
    )

