"""Read model do Dashboard F1 baseado na integração histórica já usada pela V3."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _records(frame: Any) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return [{str(key): (None if pd.isna(value) else value) for key, value in row.items()} for row in frame.to_dict("records")]


def build_f1_dashboard(season: str) -> dict[str, Any]:
    """Carrega estatísticas oficiais sem misturá-las aos dados do bolão."""
    from utils.data_utils import (
        get_constructor_standings,
        get_driver_points_by_race,
        get_driver_standings,
        get_fastest_lap_times,
        get_pit_stop_data,
        get_qualifying_vs_race_delta,
    )

    drivers = get_driver_standings(season)
    constructors = get_constructor_standings(season)
    progression = get_driver_points_by_race(season)
    qualifying = get_qualifying_vs_race_delta(season)
    fastest = get_fastest_lap_times(season)
    pit_stops = get_pit_stop_data(season)

    progression_rows: list[dict[str, Any]] = []
    progression_drivers: list[str] = []
    if isinstance(progression, pd.DataFrame) and not progression.empty:
        progression_drivers = [str(column) for column in progression.columns if column not in {"Round", "Race"}]
        for row in progression.to_dict("records"):
            progression_rows.append({
                "round": int(row.get("Round") or 0),
                "race": str(row.get("Race") or ""),
                "points": {driver: float(row.get(driver) or 0) for driver in progression_drivers},
            })

    driver_rows = [
        {"position": int(row.get("Position") or 0), "driver": str(row.get("Driver") or ""), "points": float(row.get("Points") or 0), "wins": int(row.get("Wins") or 0), "nationality": str(row.get("Nationality") or ""), "constructor": str(row.get("Constructor") or "")}
        for row in _records(drivers)
    ]
    constructor_rows = [
        {"position": int(row.get("Position") or 0), "constructor": str(row.get("Constructor") or ""), "points": float(row.get("Points") or 0), "wins": int(row.get("Wins") or 0), "nationality": str(row.get("Nationality") or "")}
        for row in _records(constructors)
    ]
    qualifying_rows = [
        {"driver": str(row.get("Driver") or ""), "qualifying": int(row.get("Qualifying") or 0), "race": int(row.get("Race") or 0), "delta": int(row.get("Delta") or 0)}
        for row in _records(qualifying)
    ]
    fastest_rows = [{"driver": str(row.get("Driver") or ""), "time": str(row.get("Fastest Lap") or "")} for row in _records(fastest)]
    pit_rows = [
        {"driver": str(row.get("Driver") or ""), "lap": int(row.get("Lap") or 0), "stop": int(row.get("Stop") or 0), "time": str(row.get("Time") or "")}
        for row in _records(pit_stops)
    ]
    average_stops = None
    if pit_rows:
        max_stops: dict[str, int] = {}
        for row in pit_rows:
            max_stops[row["driver"]] = max(max_stops.get(row["driver"], 0), row["stop"])
        average_stops = sum(max_stops.values()) / len(max_stops)

    return {
        "season": str(season),
        "driver_standings": driver_rows,
        "constructor_standings": constructor_rows,
        "progression_drivers": progression_drivers,
        "progression": progression_rows,
        "qualifying_vs_race": qualifying_rows,
        "fastest_laps": fastest_rows,
        "pit_stops": pit_rows,
        "average_stops": average_stops,
    }


__all__ = ["build_f1_dashboard"]
