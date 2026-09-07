"""Casos de uso HTTP de autenticação sem dependência de UI."""

from __future__ import annotations

from datetime import datetime, timedelta

from utils.security_utils import normalize_email_identifier


def recent_failures(email: str, ip_address: str, *, action: str, max_attempts: int, lockout_seconds: int) -> tuple[int, int, bool]:
    from db.db_schema import db_connect
    email = normalize_email_identifier(email)
    since = datetime.now() - timedelta(seconds=lockout_seconds)
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM login_attempts WHERE email=%s AND tentativa_em>%s AND action=%s AND sucesso IS NOT TRUE", (email, since, action))
        email_count = int((cur.fetchone() or {}).get("n") or 0)
        cur.execute("SELECT COUNT(*) AS n FROM login_attempts WHERE ip_address=%s AND tentativa_em>%s AND action=%s AND sucesso IS NOT TRUE", (ip_address, since, action))
        ip_count = int((cur.fetchone() or {}).get("n") or 0)
    return email_count, ip_count, email_count >= max_attempts or ip_count >= max_attempts * 3


def record_attempt(email: str, success: bool, ip_address: str, action: str = "login") -> None:
    from db.db_schema import db_connect
    with db_connect() as conn:
        conn.cursor().execute("INSERT INTO login_attempts(email,sucesso,ip_address,action) VALUES (%s,%s,%s,%s)", (normalize_email_identifier(email), success, ip_address, action))
        conn.commit()


def record_access(*, event: str, success: bool, ip_address: str, user: dict | None = None, detail: str | None = None) -> None:
    try:
        from db.db_schema import db_connect
        user = user or {}
        with db_connect() as conn:
            conn.cursor().execute(
                """INSERT INTO access_logs(evento,sucesso,user_id,email,nome,perfil,ip_address,detalhes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (event, success, user.get("id"), user.get("email"), user.get("nome"), user.get("perfil"), ip_address, detail),
            )
            conn.commit()
    except Exception:
        pass

