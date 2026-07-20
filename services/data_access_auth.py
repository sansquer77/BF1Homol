"""Fachada de dados de autenticacao/usuarios para a camada de UI."""

import streamlit as st

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
    registrar_historico_status_usuario,
    update_user_email,
    update_user_password,
    usuarios_status_historico_disponivel,
)


@st.cache_data(ttl=60, show_spinner=False)
def get_usuarios_df():
    return _repo_get_usuarios_df()


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
