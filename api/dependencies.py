"""Dependências de identidade e autorização da API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from api.config import settings
from services.access_control import AuthenticatedContext, AuthorizationDenied, authorize_context

_PASSWORD_CHANGE_ALLOWED_PATHS = {
    "/api/v1/auth/me",
    "/api/v1/auth/account/password",
    "/api/v1/auth/logout",
}


def get_current_context(request: Request) -> AuthenticatedContext:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    from db.repo_users import get_user_by_id, get_usuario_temporadas_ativas
    from services.auth_service import decode_token

    payload = decode_token(token)
    user = get_user_by_id(int(payload["user_id"])) if payload and payload.get("user_id") else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    perfil = str(user.get("perfil") or "participante").strip().lower()
    db_status = str(user.get("status") or "").strip().lower()
    if db_status != "ativo" or perfil == "inativo":
        perfil = "inativo"
    if perfil == "inativo":
        seasons = frozenset(str(v) for v in get_usuario_temporadas_ativas(int(user["id"])))
    elif perfil == "participante":
        from datetime import datetime
        seasons = frozenset({str(datetime.now().year)})
    else:
        seasons = frozenset()
    tz = str(user.get("timezone") or "America/Sao_Paulo").strip()
    if not tz:
        tz = "America/Sao_Paulo"
    must_change = bool(user.get("must_change_password") or False)
    if must_change and request.url.path not in _PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troca de senha obrigatória antes de continuar.",
        )
    context = AuthenticatedContext(int(user["id"]), str(user.get("nome") or ""), perfil, db_status, seasons, tz, must_change)
    request.state.auth = context
    return context


def require_master(context: AuthenticatedContext = Depends(get_current_context)) -> AuthenticatedContext:
    try:
        authorize_context(context, frozenset({"master"}))
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.") from exc
    return context


def authorize_user_object(target_user_id: int, context: AuthenticatedContext) -> None:
    """Evita IDOR: somente o próprio usuário ou Master consulta o objeto."""
    if context.user_id != int(target_user_id) and context.perfil != "master":
        # 404 evita confirmar a existência do objeto fora do escopo.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")


def authorize_season_object(target_season: str, context: AuthenticatedContext) -> None:
    """Nega objetos de temporada fora do escopo sem confirmar sua existência."""
    if context.perfil not in {"master", "admin"} and str(target_season) not in context.temporadas_autorizadas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")
