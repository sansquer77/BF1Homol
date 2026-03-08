import re
from datetime import datetime
from zoneinfo import ZoneInfo

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def now_sao_paulo() -> datetime:
    return datetime.now(SAO_PAULO_TZ)


def normalize_time_string(time_str: str | None) -> str | None:
    if not time_str:
        return None

    raw = str(time_str).strip().lower().replace("h", ":")
    if not raw:
        return None

    match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", raw)
    if not match:
        return None

    value = match.group(1)
    parts = value.split(":")
    if len(parts[0]) == 1:
        parts[0] = parts[0].zfill(2)
    return ":".join(parts)


def parse_datetime_sao_paulo(date_str: str, time_str: str) -> datetime:
    normalized_time = normalize_time_string(time_str)
    if not normalized_time:
        raise ValueError(f"Formato de hora inválido: '{time_str}'")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            date_time = datetime.strptime(f"{date_str} {normalized_time}", fmt)
            return date_time.replace(tzinfo=SAO_PAULO_TZ)
        except ValueError:
            continue

    raise ValueError(f"Formato de data/hora inválido: '{date_str} {normalized_time}'")
