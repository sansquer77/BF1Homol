"""Fachada de dados de autenticacao/usuarios para a camada de UI."""

from db.db_config import (
    LOCKOUT_DURATION,
    MAX_LOGIN_ATTEMPTS,
    MAX_RESET_ATTEMPTS,
    RESET_LOCKOUT_DURATION,
)
from db.repo_users import (
    check_password,
    get_user_by_email,
    get_user_by_id,
    get_usuarios_df,
    registrar_historico_status_usuario,
    update_user_email,
    update_user_password,
    usuarios_status_historico_disponivel,
)

__all__ = [
    "LOCKOUT_DURATION",
    "MAX_LOGIN_ATTEMPTS",
    "MAX_RESET_ATTEMPTS",
    "RESET_LOCKOUT_DURATION",
    "check_password",
    "get_user_by_email",
    "get_user_by_id",
    "get_usuarios_df",
    "registrar_historico_status_usuario",
    "update_user_email",
    "update_user_password",
    "usuarios_status_historico_disponivel",
]
