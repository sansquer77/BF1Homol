"""Repositório focado em usuários.

Mantém compatibilidade delegando para db.db_utils.
"""

from db.db_utils import (
    autenticar_usuario,
    cadastrar_usuario,
    check_password,
    delete_usuario,
    get_master_user,
    get_user_by_email,
    get_user_by_id,
    get_usuario_temporadas_ativas,
    get_usuarios_df,
    hash_password,
    registrar_historico_status_usuario,
    update_user_email,
    update_user_password,
    update_usuario,
    usuarios_status_historico_disponivel,
)

__all__ = [
    "hash_password",
    "check_password",
    "get_user_by_email",
    "get_user_by_id",
    "get_master_user",
    "cadastrar_usuario",
    "autenticar_usuario",
    "update_user_email",
    "update_user_password",
    "update_usuario",
    "delete_usuario",
    "get_usuarios_df",
    "usuarios_status_historico_disponivel",
    "registrar_historico_status_usuario",
    "get_usuario_temporadas_ativas",
]
