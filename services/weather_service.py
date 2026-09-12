"""Previsão da próxima prova via Open-Meteo com falha isolada e cache curto."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Any

import requests

logger = logging.getLogger(__name__)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 6
MAX_FORECAST_DAYS = 16
_CACHE_TTL_SECONDS = 30 * 60
_cache: dict[tuple[float, float, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = Lock()

_WMO: tuple[tuple[set[int], str, str], ...] = (
    ({0}, "clear-day", "Céu limpo"),
    ({1, 2}, "partly-cloudy-day", "Parcialmente nublado"),
    ({3}, "overcast", "Nublado"),
    ({45, 48}, "fog", "Nevoeiro"),
    ({51, 53, 55, 56, 57}, "drizzle", "Garoa"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "rain", "Chuva"),
    ({71, 73, 75, 77, 85, 86}, "snow", "Neve"),
    ({95, 96, 99}, "thunderstorms-rain", "Trovoadas"),
)


def describe_weather_code(code: int) -> tuple[str, str]:
    for codes, icon, label in _WMO:
        if code in codes:
            return icon, label
    return "not-available", "Condição não identificada"


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def get_race_weather(latitude: float, longitude: float, starts_at: datetime, *, now: datetime) -> dict[str, Any]:
    """Obtém o ponto horário mais próximo da largada, se dentro da janela."""
    if starts_at < now - timedelta(hours=3):
        return _unavailable("A prova já ocorreu.")
    if starts_at > now + timedelta(days=MAX_FORECAST_DAYS):
        return _unavailable("A previsão estará disponível até 16 dias antes da prova.")

    cache_key = (round(latitude, 4), round(longitude, 4), starts_at.isoformat())
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,wind_speed_10m",
        "timezone": "America/Sao_Paulo",
        "start_date": starts_at.date().isoformat(),
        "end_date": starts_at.date().isoformat(),
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            return _unavailable("Previsão ainda indisponível para esta prova.")
        target = starts_at.replace(tzinfo=None)
        index = min(range(len(times)), key=lambda item: abs(datetime.fromisoformat(times[item]) - target))
        code = int(hourly["weather_code"][index])
        icon, condition = describe_weather_code(code)
        result = {
            "available": True,
            "reason": None,
            "forecast_at": times[index],
            "condition": condition,
            "icon": icon,
            "temperature_c": round(float(hourly["temperature_2m"][index]), 1),
            "apparent_temperature_c": round(float(hourly["apparent_temperature"][index]), 1),
            "precipitation_probability": int(hourly["precipitation_probability"][index]),
            "wind_speed_kmh": round(float(hourly["wind_speed_10m"][index]), 1),
        }
        with _cache_lock:
            _cache[cache_key] = (monotonic(), result)
        return result
    except Exception as exc:
        logger.warning("Previsão meteorológica indisponível: %s", type(exc).__name__)
        return _unavailable("Previsão temporariamente indisponível.")
