"""Consulta/exportação administrativa da observabilidade."""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response

from api.config import settings
from api.dependencies import authorize_season_object, get_current_context, require_master
from api.schemas import AccessLogsResponse, BettingLogsResponse
from db.repo_observability import export_events, record_event
from services.access_control import AuthenticatedContext

router = APIRouter(prefix="/logs", tags=["logs"])


def _json_default(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@router.get("/bets", response_model=BettingLogsResponse)
def betting_logs(
    season: str = Query(pattern=r"^\d{4}$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    bettor: str | None = Query(default=None, max_length=120),
    bet_type: int | None = Query(default=None, ge=0, le=1),
    event_date: date | None = Query(default=None),
    log_status: str | None = Query(default=None, max_length=80),
    automatic_only: bool = Query(default=False),
    context: AuthenticatedContext = Depends(get_current_context),
) -> BettingLogsResponse:
    """Consulta o log consolidado ou somente as apostas do usuário autenticado."""
    from services.logs_read_service import list_betting_logs

    authorize_season_object(season, context)
    scope_user_id = context.user_id if context.perfil in {"participante", "inativo"} else None
    result = list_betting_logs(
        season,
        scope_user_id=scope_user_id,
        page=page,
        page_size=page_size,
        bettor=bettor,
        bet_type=bet_type,
        event_date=event_date,
        log_status=log_status,
        automatic_only=automatic_only,
    )
    return BettingLogsResponse.model_validate(result)


@router.get("/access", response_model=AccessLogsResponse)
def access_logs(
    start: date,
    end: date,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    profile: str | None = Query(default=None, max_length=40),
    event: str | None = Query(default=None, max_length=100),
    success: bool | None = Query(default=None),
    ip_contains: str | None = Query(default=None, max_length=64),
    user_contains: str | None = Query(default=None, max_length=254),
    context: AuthenticatedContext = Depends(require_master),
) -> AccessLogsResponse:
    """Consulta exclusiva do Master, com intervalo e paginação limitados."""
    from services.logs_read_service import list_access_logs

    try:
        result = list_access_logs(start, end, page=page, page_size=page_size, profile=profile, event=event, success=success, ip_contains=ip_contains, user_contains=user_contains)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AccessLogsResponse.model_validate(result)


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
