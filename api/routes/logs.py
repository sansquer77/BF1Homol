"""Consulta/exportação administrativa da observabilidade."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response

from api.config import settings
from api.dependencies import require_master
from db.repo_observability import export_events, record_event
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/logs", tags=["logs"])


def _json_default(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@router.get("/export")
def export_logs(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    reauth_password: str = Header(alias="X-Reauth-Password", min_length=1, max_length=1024),
    context: AuthenticatedContext = Depends(require_master),
) -> Response:
    """Gera JSONL gzip em memória; não aceita nomes ou caminhos do cliente."""
    from db.repo_users import check_password, get_user_by_id
    user = get_user_by_id(context.user_id)
    if not user or not check_password(reauth_password, str(user.get("senha_hash") or user.get("senha") or "")):
        record_event(level="WARNING", category="security", event="log_export_reauth_failed", message="Reautenticação de exportação falhou", user_id=context.user_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reautenticação necessária.")
    now = datetime.now(timezone.utc)
    start = start or (now - timedelta(days=1))
    end = end or now
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end <= start or end - start > timedelta(days=31):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Intervalo inválido ou superior a 31 dias.")
    rows = list(export_events(start=start, end=end, limit=settings.log_export_limit))
    body = "".join(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n" for row in rows).encode("utf-8")
    compressed = gzip.compress(body)
    record_event(level="INFO", category="security", event="log_exported", message="Exportação administrativa de logs", user_id=context.user_id, metadata={"rows": len(rows), "start": start, "end": end})
    filename = f"bf1-logs-{now:%Y%m%dT%H%M%SZ}.jsonl.gz"
    return Response(compressed, media_type="application/gzip", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})

