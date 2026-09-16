"""Verificação rate-limited de senha para operações administrativas críticas."""

from __future__ import annotations

import logging

from db.db_config import REAUTH_LOCKOUT_DURATION, MAX_REAUTH_ATTEMPTS

logger = logging.getLogger(__name__)

CRITICAL_REAUTH_ACTION = "critical_reauth"


class CriticalReauthenticationFailed(PermissionError):
    """A senha crítica não foi confirmada."""


class CriticalReauthenticationBlocked(CriticalReauthenticationFailed):
    """A conta ou origem atingiu o limite temporário de reautenticação."""


def _audit(*, event: str, user_id: int) -> None:
    """Registra o desfecho sem tornar a auditoria secundária um novo oráculo."""
    try:
        from db.repo_observability import record_event

        record_event(
            level="WARNING",
            category="security",
            event=event,
            message="Reautenticação administrativa crítica recusada",
            user_id=user_id,
        )
    except Exception as exc:  # pragma: no cover - contingência já coberta pelo logger
        logger.warning("Falha ao auditar reautenticação crítica: %s", type(exc).__name__)


def verify_critical_password(user_id: int, password: str, *, ip_address: str | None = None) -> dict:
    """Confirma a senha com um único bucket compartilhado por conta e IP.

    A leitura e a gravação do limitador são fail-closed: se o PostgreSQL não
    puder aplicar o controle, a operação crítica não recebe autorização.
    """
    # spec: autenticacao-e-sessao v1.6 — critérios 12 e 13
    from db.repo_users import check_password, get_user_by_id

    user = get_user_by_id(int(user_id))
    email = str((user or {}).get("email") or f"user-{int(user_id)}@invalid.local")
    ip = str(ip_address or "unknown")
    from db.repo_auth_attempts import perform_rate_limited_attempt

    candidate = password if isinstance(password, str) else ""
    password_hash = str((user or {}).get("senha_hash") or (user or {}).get("senha") or "")
    outcome = perform_rate_limited_attempt(
        email,
        ip,
        action=CRITICAL_REAUTH_ACTION,
        max_attempts=MAX_REAUTH_ATTEMPTS,
        lockout_seconds=REAUTH_LOCKOUT_DURATION,
        verify=lambda: bool(
            candidate
            and len(candidate) <= 1024
            and user
            and check_password(candidate, password_hash)
        ),
    )
    if outcome == "blocked":
        _audit(event="critical_reauth_blocked", user_id=int(user_id))
        raise CriticalReauthenticationBlocked("Não foi possível confirmar a senha.")
    if outcome != "success":
        _audit(event="critical_reauth_failed", user_id=int(user_id))
        raise CriticalReauthenticationFailed("Não foi possível confirmar a senha.")
    return user


__all__ = [
    "CRITICAL_REAUTH_ACTION",
    "CriticalReauthenticationBlocked",
    "CriticalReauthenticationFailed",
    "verify_critical_password",
]
