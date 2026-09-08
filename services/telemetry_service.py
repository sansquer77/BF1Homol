"""Snapshot de leitura da Telemetria V4, sem dependência de Streamlit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from services.painel_controller import ordenar_provas_por_calendario, parse_evento_prova_dt
from utils.datetime_utils import now_sao_paulo


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return frame.to_dict("records")


def _number(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(parsed) else float(parsed)


def build_telemetry_snapshot(
    user_id: int,
    user_name: str,
    season: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Monta o resumo apenas com dados persistidos pelo comportamento V3."""
    from db.repo_bets import get_apostas_df, get_participantes_temporada_df, get_posicoes_participantes_df
    from db.repo_races import get_provas_df

    season = str(season)
    now_sp = now or now_sao_paulo()
    races = get_provas_df(season)
    bets = get_apostas_df(season)
    positions = get_posicoes_participantes_df(season)
    participants = get_participantes_temporada_df(season)

    ordered = ordenar_provas_por_calendario(races) if isinstance(races, pd.DataFrame) else pd.DataFrame()
    race_rows = _records(ordered)
    race_order: dict[int, int] = {}
    race_names: dict[int, str] = {}
    next_race: dict[str, Any] | None = None
    for index, row in enumerate(race_rows):
        try:
            race_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        race_order[race_id] = index
        race_names[race_id] = str(row.get("nome") or f"Prova {race_id}")
        event_at = parse_evento_prova_dt(row.get("data"), row.get("horario_prova"), now_sp.tzinfo)
        if next_race is None and event_at is not None and event_at >= now_sp:
            next_race = {
                "id": race_id,
                "name": race_names[race_id],
                "round": index + 1,
                "date": event_at.date().isoformat(),
                "time": event_at.strftime("%H:%M"),
                "starts_at": event_at.isoformat(),
                "type": str(row.get("tipo") or "Normal"),
                "circuit_id": str(row.get("circuit_id")) if row.get("circuit_id") else None,
            }

    position_rows = []
    for row in _records(positions):
        try:
            row_user_id = int(row.get("usuario_id"))
            race_id = int(row.get("prova_id"))
        except (TypeError, ValueError):
            continue
        if race_id not in race_order:
            continue
        position_rows.append({
            "user_id": row_user_id,
            "race_id": race_id,
            "position": int(_number(row.get("posicao"))) if _number(row.get("posicao")) else None,
            "points": _number(row.get("pontos")),
            "order": race_order[race_id],
        })

    own_rows = sorted((row for row in position_rows if row["user_id"] == int(user_id)), key=lambda row: row["order"])
    cumulative = 0.0
    evolution = []
    for row in own_rows:
        cumulative += row["points"]
        evolution.append({
            "race_id": row["race_id"],
            "race_name": race_names.get(row["race_id"], f"Prova {row['race_id']}"),
            "position": row["position"],
            "points": row["points"],
            "cumulative_points": round(cumulative, 2),
        })

    names: dict[int, str] = {int(user_id): str(user_name)}
    for row in _records(participants):
        try:
            names[int(row.get("id"))] = str(row.get("nome") or "Participante")
        except (TypeError, ValueError):
            continue

    totals: dict[int, float] = {}
    for row in position_rows:
        totals[row["user_id"]] = totals.get(row["user_id"], 0.0) + row["points"]
    ranking = []
    for rank, (rank_user_id, points) in enumerate(sorted(totals.items(), key=lambda item: (-item[1], names.get(item[0], "")))[:3], start=1):
        ranking.append({
            "position": rank,
            "name": names.get(rank_user_id, "Participante"),
            "points": round(points, 2),
            "is_current_user": rank_user_id == int(user_id),
        })

    own_bet_races: set[int] = set()
    for row in _records(bets):
        try:
            if int(row.get("usuario_id")) == int(user_id):
                own_bet_races.add(int(row.get("prova_id")))
        except (TypeError, ValueError):
            continue

    return {
        "user_name": str(user_name),
        "season": season,
        "next_race": next_race,
        "metrics": {
            "current_position": own_rows[-1]["position"] if own_rows else None,
            "points": round(sum(row["points"] for row in own_rows), 2),
            "bets_submitted": len(own_bet_races),
            "races_total": len(race_order),
        },
        "evolution": evolution,
        "ranking": ranking,
    }


__all__ = ["build_telemetry_snapshot"]
