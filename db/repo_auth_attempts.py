"""Persistência atômica de tentativas de autenticação sensíveis."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Literal

from utils.security_utils import normalize_email_identifier

AttemptOutcome = Literal["success", "failed", "blocked"]


def perform_rate_limited_attempt(
    email: str,
    ip_address: str,
    *,
    action: str,
    max_attempts: int,
    lockout_seconds: int,
    verify: Callable[[], bool],
) -> AttemptOutcome:
    """Serializa conta/IP, verifica o limite e persiste o resultado na transação."""
    from db.db_schema import db_connect

    normalized_email = normalize_email_identifier(email)
    ip = str(ip_address)
    since = datetime.now() - timedelta(seconds=lockout_seconds)
    with db_connect() as conn:
        cur = conn.cursor()
        # Locks transacionais evitam que chamadas concorrentes observem o mesmo
        # contador antes de gravarem seus resultados. A ordem é sempre conta/IP.
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"bf1:{action}:account:{normalized_email}",),
        )
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"bf1:{action}:ip:{ip}",),
        )
        cur.execute(
            "SELECT COUNT(*) AS n FROM login_attempts WHERE email=%s AND tentativa_em>%s AND action=%s AND sucesso IS NOT TRUE",
            (normalized_email, since, action),
        )
        email_count = int((cur.fetchone() or {}).get("n") or 0)
        cur.execute(
            "SELECT COUNT(*) AS n FROM login_attempts WHERE ip_address=%s AND tentativa_em>%s AND action=%s AND sucesso IS NOT TRUE",
            (ip, since, action),
        )
        ip_count = int((cur.fetchone() or {}).get("n") or 0)
        blocked = email_count >= max_attempts or ip_count >= max_attempts * 3
        success = False if blocked else bool(verify())
        cur.execute(
            "INSERT INTO login_attempts(email,sucesso,ip_address,action) VALUES (%s,%s,%s,%s)",
            (normalized_email, success, ip, action),
        )
        conn.commit()
    if blocked:
        return "blocked"
    return "success" if success else "failed"


__all__ = ["AttemptOutcome", "perform_rate_limited_attempt"]
