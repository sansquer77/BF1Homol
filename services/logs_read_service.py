"""Consultas paginadas dos logs V4, sem dependência da camada de entrega."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Any


def _pagination(total: int, requested_page: int, page_size: int) -> dict[str, int]:
    size = max(1, min(int(page_size), 200))
    pages = max(1, ceil(max(0, int(total)) / size))
    page = min(max(1, int(requested_page)), pages)
    return {"page": page, "page_size": size, "total": int(total), "total_pages": pages}


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _row(row: Any) -> dict[str, Any]:
    return {str(key): _json_value(value) for key, value in dict(row).items()}


def list_betting_logs(
    season: str,
    *,
    scope_user_id: int | None,
    page: int = 1,
    page_size: int = 50,
    bettor: str | None = None,
    bet_type: int | None = None,
    event_date: date | None = None,
    log_status: str | None = None,
    automatic_only: bool = False,
) -> dict[str, Any]:
    """Lista apostas auditadas; o escopo individual vem da identidade autenticada."""
    from db.db_schema import db_connect, get_table_columns

    with db_connect() as conn:
        columns = set(get_table_columns(conn, "log_apostas"))
        user_col = "usuario_id" if "usuario_id" in columns else ("user_id" if "user_id" in columns else None)
        if scope_user_id is not None and user_col is None:
            return {"season": str(season), "scope": "individual", "pagination": _pagination(0, page, page_size), "items": []}

        status_expr = "status" if "status" in columns else "'Registrada'"
        ip_expr = "ip_address" if "ip_address" in columns else "NULL"
        user_expr = user_col or "NULL"
        season_sources = [
            expression for column, expression in (
                ("temporada", "NULLIF(TRIM(CAST(temporada AS TEXT)), '')"),
                ("data", "NULLIF(SUBSTR(CAST(data AS TEXT), 1, 4), '')"),
                ("data_criacao", "NULLIF(SUBSTR(CAST(data_criacao AS TEXT), 1, 4), '')"),
            ) if column in columns
        ]
        where: list[str] = []
        params: list[Any] = []
        if season_sources:
            where.append(f"COALESCE({', '.join(season_sources)}) = %s")
            params.append(str(season))
        if scope_user_id is not None:
            where.append(f"{user_col} = %s")
            params.append(int(scope_user_id))
        if bettor and scope_user_id is None:
            where.append("LOWER(COALESCE(apostador, '')) LIKE %s")
            params.append(f"%{bettor.strip().lower()}%")
        if bet_type is not None:
            where.append("tipo_aposta = %s")
            params.append(int(bet_type))
        if event_date is not None:
            where.append("SUBSTR(CAST(data AS TEXT), 1, 10) = %s")
            params.append(event_date.isoformat())
        if log_status:
            where.append(f"{status_expr} = %s")
            params.append(log_status.strip())
        if automatic_only:
            where.append("COALESCE(automatica, 0) > 0")
        where_sql = " WHERE " + " AND ".join(where) if where else ""

        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS total FROM log_apostas{where_sql}", tuple(params))
        total = int((cursor.fetchone() or {}).get("total") or 0)
        pagination = _pagination(total, page, page_size)
        offset = (pagination["page"] - 1) * pagination["page_size"]
        cursor.execute(
            "SELECT id, "
            f"{user_expr} AS usuario_id, data, horario, apostador, nome_prova, pilotos, aposta, "
            f"piloto_11, tipo_aposta, automatica, {ip_expr} AS ip_address, temporada, "
            f"{status_expr} AS status FROM log_apostas{where_sql} "
            "ORDER BY id DESC LIMIT %s OFFSET %s",
            tuple([*params, pagination["page_size"], offset]),
        )
        items = [_row(item) for item in (cursor.fetchall() or [])]
        cursor.close()
    return {"season": str(season), "scope": "individual" if scope_user_id is not None else "all", "pagination": pagination, "items": items}


def list_access_logs(
    start: date,
    end: date,
    *,
    page: int = 1,
    page_size: int = 50,
    profile: str | None = None,
    event: str | None = None,
    success: bool | None = None,
    ip_contains: str | None = None,
    user_contains: str | None = None,
) -> dict[str, Any]:
    """Lista acessos para o fluxo Master; autorização ocorre antes desta chamada."""
    from db.db_schema import db_connect

    if end < start or end - start > timedelta(days=31):
        raise ValueError("Intervalo inválido ou superior a 31 dias.")
    start_at = datetime.combine(start, time.min)
    end_at = datetime.combine(end + timedelta(days=1), time.min)
    where = ["created_at >= %s", "created_at < %s"]
    params: list[Any] = [start_at, end_at]
    if profile:
        where.append("LOWER(COALESCE(perfil, '')) = %s")
        params.append(profile.strip().lower())
    if event:
        where.append("evento = %s")
        params.append(event.strip())
    if success is not None:
        where.append("sucesso = %s")
        params.append(success)
    if ip_contains:
        where.append("LOWER(COALESCE(ip_address, '')) LIKE %s")
        params.append(f"%{ip_contains.strip().lower()}%")
    if user_contains:
        token = f"%{user_contains.strip().lower()}%"
        where.append("(LOWER(COALESCE(email, '')) LIKE %s OR LOWER(COALESCE(nome, '')) LIKE %s)")
        params.extend([token, token])
    where_sql = " AND ".join(where)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE sucesso IS TRUE) AS successes, "
            f"COUNT(*) FILTER (WHERE sucesso IS NOT TRUE) AS failures FROM access_logs WHERE {where_sql}",
            tuple(params),
        )
        summary = cursor.fetchone() or {}
        pagination = _pagination(int(summary.get("total") or 0), page, page_size)
        offset = (pagination["page"] - 1) * pagination["page_size"]
        cursor.execute(
            "SELECT id, created_at, evento, sucesso, user_id, email, nome, perfil, ip_address, detalhes "
            f"FROM access_logs WHERE {where_sql} ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
            tuple([*params, pagination["page_size"], offset]),
        )
        items = [_row(item) for item in (cursor.fetchall() or [])]
        cursor.close()
    return {"pagination": pagination, "successes": int(summary.get("successes") or 0), "failures": int(summary.get("failures") or 0), "items": items}


__all__ = ["list_access_logs", "list_betting_logs"]
