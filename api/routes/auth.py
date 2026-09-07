"""Contrato HTTP de autenticação e sessão."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi import HTTPException

from api.auth_backend import recent_failures, record_access, record_attempt
from api.config import settings
from api.dependencies import get_current_context
from api.schemas import LoginRequest, MessageResponse, PasswordResetConfirm, PasswordResetRequest, UserResponse
from api.security import clear_session_cookies, issue_session_cookies
from db.db_config import LOCKOUT_DURATION, MAX_LOGIN_ATTEMPTS, MAX_RESET_ATTEMPTS, RESET_LOCKOUT_DURATION
from services.access_control import AuthenticatedContext
from utils.security_utils import normalize_email_identifier

router = APIRouter(prefix="/auth", tags=["auth"])
GENERIC_LOGIN = "Email ou senha inválidos."
GENERIC_RESET = "Se o email estiver cadastrado, você receberá as instruções em instantes."


def _user_response(user: dict) -> UserResponse:
    return UserResponse(id=int(user["id"]), nome=str(user.get("nome") or ""), email=str(user.get("email") or ""),
                        perfil=str(user.get("perfil") or "participante").lower(), status=str(user.get("status") or "").lower(),
                        must_change_password=bool(user.get("must_change_password") or False))


@router.post("/login", response_model=UserResponse, responses={401: {"description": GENERIC_LOGIN}})
def login(payload: LoginRequest, request: Request, response: Response) -> UserResponse:
    from db.repo_users import check_password, get_user_by_email
    from services.auth_service import generate_token
    email = normalize_email_identifier(str(payload.email))
    ip = request.state.client_ip or "unknown"
    _, _, blocked = recent_failures(email, ip, action="login", max_attempts=MAX_LOGIN_ATTEMPTS, lockout_seconds=LOCKOUT_DURATION)
    if blocked:
        record_attempt(email, False, ip)
        record_access(event="login_blocked", success=False, ip_address=ip, detail="rate_limit")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=GENERIC_LOGIN)
    user = get_user_by_email(email)
    # Hash constante reduz diferença observável entre conta ausente e senha inválida.
    candidate_hash = (user or {}).get("senha_hash") or "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxccqZc9dHIi7zX3aR6Qf3S6k6u"
    valid = check_password(payload.password, candidate_hash)
    if not user or not valid or str(user.get("status") or "").lower() != "ativo":
        record_attempt(email, False, ip)
        record_access(event="login_failed", success=False, ip_address=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN)
    token = generate_token(int(user["id"]), str(user.get("nome") or ""), str(user.get("perfil") or ""), str(user.get("status") or ""))
    record_attempt(email, True, ip)
    record_access(event="login_success", success=True, ip_address=ip, user=user)
    issue_session_cookies(response, token)
    return _user_response(user)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, _: AuthenticatedContext = Depends(get_current_context)) -> MessageResponse:
    from services.auth_service import revoke_token
    revoke_token(request.cookies.get(settings.cookie_name))
    clear_session_cookies(response)
    return MessageResponse(message="Sessão encerrada.")


@router.get("/me", response_model=UserResponse)
def me(context: AuthenticatedContext = Depends(get_current_context)) -> UserResponse:
    from db.repo_users import get_user_by_id
    user = get_user_by_id(context.user_id)
    return _user_response(user)


@router.post("/password-reset", response_model=MessageResponse)
def request_password_reset(payload: PasswordResetRequest, request: Request) -> MessageResponse:
    from services.auth_service import redefinir_senha_usuario
    email = normalize_email_identifier(str(payload.email))
    ip = request.state.client_ip or "unknown"
    _, _, blocked = recent_failures(email, ip, action="password_reset", max_attempts=MAX_RESET_ATTEMPTS, lockout_seconds=RESET_LOCKOUT_DURATION)
    if not blocked:
        ok, result = redefinir_senha_usuario(email)
        if ok:
            from services.email_service import enviar_email_recuperacao_senha
            nome, token, minutes = result
            enviar_email_recuperacao_senha(email, nome, token, minutes)
    record_attempt(email, False, ip, "password_reset")
    return MessageResponse(message=GENERIC_RESET)


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(payload: PasswordResetConfirm) -> MessageResponse:
    from services.auth_service import redefinir_senha_com_token
    ok, _ = redefinir_senha_com_token(str(payload.email), payload.token, payload.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido ou expirado.")
    return MessageResponse(message="Senha redefinida com sucesso.")

