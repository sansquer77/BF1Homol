"""Alterações autenticadas da própria conta na V4."""
from services.access_control import AuthenticatedContext, AuthorizationDenied
from utils.security_utils import normalize_email_identifier


def _verified_user(context: AuthenticatedContext, current_password: str) -> dict:
    # spec: autenticacao-e-sessao v1.6 — critério 13
    from db.repo_users import check_password, get_user_by_id
    user = get_user_by_id(context.user_id)
    if str((user or {}).get("perfil") or "").lower() == "master":
        raise ValueError("As credenciais do Master são administradas pelas variáveis de ambiente.")
    if not user or not check_password(current_password, str(user.get("senha_hash") or "")):
        raise AuthorizationDenied("Senha atual inválida.")
    return user


def change_own_email(context: AuthenticatedContext, current_password: str, new_email: str) -> dict:
    from db.repo_users import get_user_by_email, update_user_email
    user = _verified_user(context, current_password)
    email = normalize_email_identifier(new_email)
    existing = get_user_by_email(email)
    if existing and int(existing["id"]) != context.user_id:
        raise ValueError("Este email já está em uso.")
    if not update_user_email(context.user_id, email):
        raise ValueError("Não foi possível alterar o email.")
    return {**user, "email": email}


def change_own_password(context: AuthenticatedContext, current_password: str, new_password: str) -> None:
    from db.repo_users import check_password, update_user_password
    from utils.validators import validar_senha
    user = _verified_user(context, current_password)
    valid, reason = validar_senha(new_password)
    if not valid:
        raise ValueError(reason)
    if check_password(new_password, str(user.get("senha_hash") or "")):
        raise ValueError("A nova senha deve ser diferente da atual.")
    if not update_user_password(context.user_id, new_password):
        raise ValueError("Não foi possível alterar a senha.")


_VALID_TIMEZONES = {
    "America/Sao_Paulo", "America/Recife", "America/Manaus", "America/Rio_Branco",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Anchorage", "Pacific/Honolulu", "UTC", "Europe/London", "Europe/Paris",
    "Europe/Berlin", "Europe/Madrid", "Europe/Rome", "Asia/Tokyo", "Asia/Dubai",
    "Australia/Sydney", "Australia/Melbourne",
}


def change_own_timezone(context: AuthenticatedContext, timezone: str) -> dict:
    from db.repo_users import get_user_by_id, update_user_timezone
    tz = str(timezone or "").strip()
    if tz not in _VALID_TIMEZONES:
        raise ValueError("Timezone inválido.")
    user = get_user_by_id(context.user_id)
    if not user:
        raise AuthorizationDenied("Usuário não encontrado.")
    if not update_user_timezone(context.user_id, tz):
        raise ValueError("Não foi possível alterar o timezone.")
    return {**user, "timezone": tz}
