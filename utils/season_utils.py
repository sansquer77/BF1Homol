from datetime import datetime
from typing import Iterable, Optional
import streamlit as st

from db.backup_utils import list_temporadas


def _normalize_season_values(values: Iterable[str]) -> list[str]:
    normalized = []
    for value in values:
        season = str(value).strip()
        if season:
            normalized.append(season)
    return normalized


def get_current_year_str() -> str:
    return str(datetime.now().year)


def get_season_options(
    fallback_years: Optional[list[str]] = None,
    include_current_year: bool = True,
    descending: bool = False,
    ensure_values: Optional[list[str]] = None,
) -> list[str]:
    seasons = _normalize_season_values(list_temporadas() or [])

    if include_current_year:
        current_year = get_current_year_str()
        if current_year not in seasons:
            seasons.append(current_year)

    if ensure_values:
        for season in _normalize_season_values(ensure_values):
            if season not in seasons:
                seasons.append(season)

    if not seasons:
        fallback = fallback_years or [get_current_year_str()]
        seasons = _normalize_season_values(fallback)

    # Restrição global para usuário inativo: apenas temporadas em que esteve ativo.
    try:
        user_status = str(st.session_state.get("user_status", "")).strip().lower()
        if user_status and user_status != "ativo":
            allowed = _normalize_season_values(st.session_state.get("allowed_seasons", []) or [])
            if allowed:
                allowed_set = set(allowed)
                seasons = [s for s in seasons if s in allowed_set]
            else:
                seasons = []
    except Exception:
        pass

    seasons = sorted(set(seasons), reverse=descending)
    return seasons


def get_default_season_index(options: list[str], current_year: Optional[str] = None) -> int:
    if not options:
        return 0
    year = current_year or get_current_year_str()
    return options.index(year) if year in options else 0
