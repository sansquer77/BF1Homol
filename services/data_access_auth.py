"""Fachada de dados de autenticacao/usuarios para a camada de UI."""

import streamlit as st
from utils.dataframe_contracts import USUARIOS_COLUMNS, with_required_columns

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
    get_usuarios_df as _repo_get_usuarios_df,
    registrar_historico_status_usuario as _registrar_historico_status_usuario,
    update_user_email as _update_user_email,
    update_user_password as _update_user_password,
    usuarios_status_historico_disponivel,
)
from services.access_control import authorize_context, require_operation, resolve_authenticated_context


def update_user_password(user_id: int, nova_senha: str, must_change_password: bool = False) -> bool:
    context = resolve_authenticated_context()
    if int(user_id) != context.user_id:
        require_operation("usuario.write")
    else:
        authorize_context(context, frozenset({"participante", "admin", "master"}))
        user_id = context.user_id
    return _update_user_password(int(user_id), nova_senha, must_change_password)


def update_user_email(user_id: int, novo_email: str) -> bool:
    context = resolve_authenticated_context()
    if int(user_id) != context.user_id:
        require_operation("usuario.write")
    else:
        authorize_context(context, frozenset({"participante", "admin", "master"}))
        user_id = context.user_id
    return _update_user_email(int(user_id), novo_email)


def registrar_historico_status_usuario(*args, **kwargs):
    require_operation("usuario.write")
    return _registrar_historico_status_usuario(*args, **kwargs)


@st.cache_data(ttl=60, show_spinner=False)
def get_usuarios_df():
    return with_required_columns(_repo_get_usuarios_df(), USUARIOS_COLUMNS)


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
