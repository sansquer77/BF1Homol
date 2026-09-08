"""Persistência best-effort de observabilidade operacional da V4."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from db.db_schema import db_connect

logger = logging.getLogger(__name__)
_SENSITIVE_KEYS = {"password", "senha", "token", "jwt", "authorization", "cookie", "secret"}


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in _SENSITIVE_KEYS for part in normalized.split("_"))


def sanitize_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key)[:80]: "[redacted]" if _is_sensitive_key(key) else sanitize_metadata(item, depth=depth + 1)
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(item, depth=depth + 1) for item in value[:50]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


def record_event(*, level: str, category: str, event: str, message: str,
                 request_id: str | None = None, user_id: int | None = None,
                 route: str | None = None, method: str | None = None,
                 status_code: int | None = None, duration_ms: float | None = None,
                 metadata: dict[str, Any] | None = None,
                 exception_class: str | None = None) -> None:
    """Grava sem propagar falha: observabilidade nunca derruba a requisição."""
    try:
        safe = sanitize_metadata(metadata or {})
        with db_connect() as conn:
            conn.cursor().execute(
                """INSERT INTO application_logs
                   (level,category,event,message,request_id,user_id,route,method,
                    status_code,duration_ms,metadata,exception_class)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (level.upper()[:10], category[:40], event[:120], message[:2000],
                 request_id, user_id, route[:500] if route else None, method[:10] if method else None,
                 status_code, duration_ms, json.dumps(safe, ensure_ascii=False),
                 exception_class[:200] if exception_class else None),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Falha ao persistir observabilidade event=%s: %s", event, type(exc).__name__)


def export_events(*, start: datetime, end: datetime, limit: int) -> Iterable[dict[str, Any]]:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id,created_at,level,category,event,message,request_id,user_id,
                      route,method,status_code,duration_ms,metadata,exception_class
               FROM application_logs WHERE created_at >= %s AND created_at < %s
               ORDER BY created_at,id LIMIT %s""",
            (start, end, limit),
        )
        for row in cur.fetchall():
            yield dict(row)


__all__ = ["record_event", "export_events", "sanitize_metadata"]
