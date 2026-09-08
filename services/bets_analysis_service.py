"""Agregados de apostas da Fase 6 sem dependência de Streamlit."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


def build_bets_analysis(season: str, *, scope_user_id: int | None) -> dict[str, Any]:
    from db.repo_bets import get_apostas_df
    from db.repo_races import get_pilotos_df, get_provas_df, get_resultados_df

    bets = get_apostas_df(str(season))
    races = get_provas_df(str(season))
    results = get_resultados_df(str(season))
    drivers = get_pilotos_df()
    if not isinstance(bets, pd.DataFrame):
        bets = pd.DataFrame()
    if scope_user_id is not None and not bets.empty and "usuario_id" in bets.columns:
        ids = pd.to_numeric(bets["usuario_id"], errors="coerce")
        bets = bets[ids == int(scope_user_id)].copy()

    teams = {}
    if isinstance(drivers, pd.DataFrame) and not drivers.empty:
        teams = {str(row.get("nome") or "").strip(): str(row.get("equipe") or "").strip() for row in drivers.to_dict("records")}

    driver_counts: dict[str, int] = defaultdict(int)
    driver_chips: dict[str, int] = defaultdict(int)
    eleventh_counts: dict[str, int] = defaultdict(int)
    bet_count = 0
    for row in bets.to_dict("records") if not bets.empty else []:
        bet_count += 1
        selected = [item.strip() for item in str(row.get("pilotos") or "").split(",") if item.strip()]
        raw_chips = [item.strip() for item in str(row.get("fichas") or "").split(",")]
        for index, driver in enumerate(selected):
            driver_counts[driver] += 1
            try:
                driver_chips[driver] += int(raw_chips[index])
            except (IndexError, TypeError, ValueError):
                pass
        eleventh = str(row.get("piloto_11") or "").strip()
        if eleventh:
            eleventh_counts[eleventh] += 1

    by_driver = [
        {"driver": name, "team": teams.get(name) or None, "bets": count, "chips": driver_chips[name]}
        for name, count in sorted(driver_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    eleventh = [
        {"driver": name, "team": teams.get(name) or None, "bets": count}
        for name, count in sorted(eleventh_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    race_count = len(races.index) if isinstance(races, pd.DataFrame) else 0
    result_count = len(results.index) if isinstance(results, pd.DataFrame) else 0
    return {
        "season": str(season),
        "scope": "individual" if scope_user_id is not None else "all",
        "bet_count": bet_count,
        "race_count": race_count,
        "result_count": result_count,
        "by_driver": by_driver,
        "eleventh": eleventh,
    }


__all__ = ["build_bets_analysis"]
