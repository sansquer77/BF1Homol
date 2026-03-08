from datetime import datetime
from typing import Iterable

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
    fallback_years: list[str] | None = None,
    include_current_year: bool = True,
    descending: bool = False,
    ensure_values: list[str] | None = None,
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

    seasons = sorted(set(seasons), reverse=descending)
    return seasons


def get_default_season_index(options: list[str], current_year: str | None = None) -> int:
    if not options:
        return 0
    year = current_year or get_current_year_str()
    return options.index(year) if year in options else 0
