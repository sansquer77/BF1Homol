"""Reautenticação em profundidade para operações de restauração de backup."""

from __future__ import annotations

import logging

from app_runtime import get_session
from services.access_control import require_operation
from utils.backup_security import (
    RestoreReauthenticationFailed,
    clear_restore_authorization,
    grant_restore_authorization,
)

logger = logging.getLogger(__name__)


def reauthorize_restore(password: str, *, ip_address: str | None = None) -> float:
    """Revalida a senha atual do master e vincula uma autorização à sessão ativa."""
    context = require_operation("backup.write")
    from services.auth_service import decode_token
    from services.critical_reauthentication import (
        CriticalReauthenticationFailed,
        verify_critical_password,
    )
    from utils.request_utils import get_client_ip

    token = get_session().get("token")
    payload = decode_token(token) if token else None
    session_matches = bool(
        payload
        and int(payload.get("user_id", 0)) == context.user_id
        and payload.get("jti")
    )
    if not session_matches:
        clear_restore_authorization()
        raise RestoreReauthenticationFailed("Não foi possível confirmar a senha.")
    try:
        verify_critical_password(
            context.user_id,
            password,
            ip_address=ip_address or get_client_ip() or "unknown",
        )
    except CriticalReauthenticationFailed as exc:
        clear_restore_authorization()
        raise RestoreReauthenticationFailed("Não foi possível confirmar a senha.") from exc

    expires_at = grant_restore_authorization(
        user_id=context.user_id,
        jti=str(payload["jti"]),
    )
    logger.info("Reautenticação para restauração concedida ao usuário id=%s", context.user_id)
    return expires_at


__all__ = ["reauthorize_restore"]
