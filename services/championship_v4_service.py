"""Read/write model do Campeonato para a API V4."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.championship_service import can_place_championship_bet
from utils.datetime_utils import now_sao_paulo


def _season(season: int | None) -> int:
    return int(season or datetime.now().year)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def build_championship_snapshot(season: int, context: AuthenticatedContext) -> dict[str, Any]:
    from db.db_schema import db_connect
    from db.repo_races import get_pilotos_df

    season_value = _season(season)
    pilots = get_pilotos_df()
    drivers: list[str] = []
    teams: list[str] = []
    if not pilots.empty:
        active = pilots[pilots.get("status", "Ativo").fillna("Ativo").astype(str).str.lower() != "inativo"] if "status" in pilots.columns else pilots
        drivers = sorted({_as_text(value) for value in active.get("nome", []).tolist() if _as_text(value)})
        teams = sorted({_as_text(value) for value in active.get("equipe", []).tolist() if _as_text(value)})
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT champion, vice, team, bet_time FROM championship_bets WHERE user_id = %s AND season = %s", (context.user_id, season_value))
        current = cursor.fetchone()
        cursor.execute("SELECT user_nome, champion, vice, team, season, bet_time FROM championship_bets_log WHERE user_id = %s AND season = %s ORDER BY bet_time DESC", (context.user_id, season_value))
        history = [dict(row) for row in (cursor.fetchall() or [])]
        all_bets: list[dict[str, Any]] = []
        result = None
        if context.perfil in {"admin", "master"}:
            cursor.execute("SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets WHERE season = %s ORDER BY user_nome, user_id", (season_value,))
            all_bets = [dict(row) for row in (cursor.fetchall() or [])]
        cursor.execute("SELECT champion, vice, team FROM championship_results WHERE season = %s", (season_value,))
        result = cursor.fetchone()
        cursor.close()
    can_bet, deadline_message, deadline = can_place_championship_bet(season_value)
    return {
        "season": str(season_value), "drivers": drivers, "teams": teams,
        "current_bet": {"season": str(season_value), **{key: current[key] for key in ("champion", "vice", "team", "bet_time")}} if current else None,
        "history": history, "all_bets": all_bets,
        "official_result": {key: result[key] for key in ("champion", "vice", "team")} if result else None,
        "can_bet": bool(can_bet), "deadline_message": deadline_message,
        "deadline": deadline.isoformat() if deadline else None,
    }


def place_championship_bet(season: int, champion: str, vice: str, team: str, context: AuthenticatedContext) -> dict[str, Any]:
    from db.db_schema import db_connect
    from db.repo_users import get_user_by_id

    season_value = _season(season)
    if context.perfil not in {"participante", "admin", "master"} or not context.ativo:
        raise AuthorizationDenied("Perfil sem permissão para apostar no campeonato.")
    champion, vice, team = _as_text(champion), _as_text(vice), _as_text(team)
    if not champion or not vice or not team or champion == vice:
        raise ValueError("Selecione campeão, vice e equipe; campeão e vice devem ser diferentes.")
    can_bet, message, _ = can_place_championship_bet(season_value)
    if not can_bet:
        raise ValueError(message)
    user = get_user_by_id(context.user_id)
    if not user or _as_text(user.get("status")).lower() != "ativo":
        raise AuthorizationDenied("Usuário inativo não pode apostar.")
    now = now_sao_paulo().strftime("%Y-%m-%d %H:%M:%S")
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO championship_bets (user_id, user_nome, champion, vice, team, season, bet_time) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id, season) DO UPDATE SET user_nome=EXCLUDED.user_nome, champion=EXCLUDED.champion, vice=EXCLUDED.vice, team=EXCLUDED.team, bet_time=EXCLUDED.bet_time",
            (context.user_id, context.nome, champion, vice, team, season_value, now),
        )
        cursor.execute(
            "INSERT INTO championship_bets_log (user_id, user_nome, champion, vice, team, season, bet_time) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (context.user_id, context.nome, champion, vice, team, season_value, now),
        )
        conn.commit()
    return {"season": str(season_value), "champion": champion, "vice": vice, "team": team, "bet_time": now}


def save_official_result(season: int, champion: str, vice: str, team: str, context: AuthenticatedContext) -> dict[str, Any]:
    from db.db_schema import db_connect

    if context.perfil not in {"admin", "master"} or not context.ativo:
        raise AuthorizationDenied("Perfil sem permissão para registrar resultado.")
    champion, vice, team = _as_text(champion), _as_text(vice), _as_text(team)
    if not champion or not vice or not team or champion == vice:
        raise ValueError("Resultado inválido: campeão e vice devem ser diferentes.")
    season_value = _season(season)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO championship_results (season, champion, vice, team) VALUES (%s,%s,%s,%s) ON CONFLICT (season) DO UPDATE SET champion=EXCLUDED.champion, vice=EXCLUDED.vice, team=EXCLUDED.team", (season_value, champion, vice, team))
        conn.commit()
    return {"season": str(season_value), "champion": champion, "vice": vice, "team": team}
