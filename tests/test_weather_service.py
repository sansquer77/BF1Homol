from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from services.weather_service import get_race_weather


def test_weather_uses_nearest_race_hour_and_maps_wmo_code():
    now = datetime(2026, 9, 12, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
    start = datetime(2026, 9, 13, 10, tzinfo=ZoneInfo("America/Sao_Paulo"))
    response = MagicMock()
    response.json.return_value = {"hourly": {
        "time": ["2026-09-13T09:00", "2026-09-13T10:00"],
        "temperature_2m": [19, 21.4], "apparent_temperature": [18, 20.1],
        "precipitation_probability": [10, 65], "weather_code": [1, 61],
        "wind_speed_10m": [7, 12.6],
    }}
    with patch("services.weather_service.requests.get", return_value=response) as request:
        result = get_race_weather(40.4, -3.7, start, now=now)
    assert result == {"available": True, "reason": None, "forecast_at": "2026-09-13T10:00", "condition": "Chuva", "icon": "rain", "temperature_c": 21.4, "apparent_temperature_c": 20.1, "precipitation_probability": 65, "wind_speed_kmh": 12.6}
    assert request.call_args.kwargs["timeout"] == 6
    assert request.call_args.kwargs["params"]["start_date"] == "2026-09-13"
    assert request.call_args.kwargs["params"]["timezone"] == "America/Sao_Paulo"


def test_weather_does_not_call_provider_outside_forecast_window():
    now = datetime(2026, 9, 12, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
    with patch("services.weather_service.requests.get") as request:
        result = get_race_weather(40.4, -3.7, now + timedelta(days=17), now=now)
    assert result["available"] is False
    assert "16 dias" in result["reason"]
    request.assert_not_called()


def test_weather_failure_is_a_valid_unavailable_state():
    now = datetime(2026, 9, 12, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
    with patch("services.weather_service.requests.get", side_effect=TimeoutError):
        result = get_race_weather(1, 1, now + timedelta(days=1), now=now)
    assert result["available"] is False
    assert "temporariamente" in result["reason"]
