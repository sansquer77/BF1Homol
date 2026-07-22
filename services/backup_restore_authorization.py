"""Reautenticação em profundidade para operações de restauração de backup."""

from __future__ import annotations

import logging

import streamlit as st

from services.access_control import require_operation
from utils.backup_security import (
    RestoreReauthenticationFailed,
    clear_restore_authorization,
    grant_restore_authorization,
)

logger = logging.getLogger(__name__)


def reauthorize_restore(password: str) -> float:
    """Revalida a senha atual do master e vincula uma autorização à sessão ativa."""
    context = require_operation("backup.write")
    candidate = password if isinstance(password, str) else ""
    if not candidate or len(candidate) > 1024:
        clear_restore_authorization()
        raise RestoreReauthenticationFailed("Não foi possível confirmar a senha.")

    from db.repo_users import check_password, get_user_by_id
    from services.auth_service import decode_token

    user = get_user_by_id(context.user_id)
    password_hash = str((user or {}).get("senha_hash") or (user or {}).get("senha") or "")
    token = st.session_state.get("token")
    payload = decode_token(token) if token else None
    session_matches = bool(
        payload
        and int(payload.get("user_id", 0)) == context.user_id
        and payload.get("jti")
    )
    if not session_matches or not check_password(candidate, password_hash):
        clear_restore_authorization()
        raise RestoreReauthenticationFailed("Não foi possível confirmar a senha.")

    expires_at = grant_restore_authorization(
        user_id=context.user_id,
        jti=str(payload["jti"]),
    )
    logger.info("Reautenticação para restauração concedida ao usuário id=%s", context.user_id)
    return expires_at


__all__ = ["reauthorize_restore"]
