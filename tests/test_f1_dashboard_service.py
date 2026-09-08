from unittest.mock import patch

import pandas as pd

from services.f1_dashboard_service import build_f1_dashboard


def test_f1_dashboard_preserves_v3_sources_and_builds_real_aggregates():
    drivers = pd.DataFrame([{"Position": 1, "Driver": "Lando Norris", "Points": 100, "Wins": 3, "Nationality": "British", "Constructor": "McLaren"}])
    constructors = pd.DataFrame([{"Position": 1, "Constructor": "McLaren", "Points": 180, "Wins": 4, "Nationality": "British"}])
    progression = pd.DataFrame([{"Round": 1, "Race": "Austrália", "Lando Norris": 25}, {"Round": 2, "Race": "China", "Lando Norris": 43}])
    qualifying = pd.DataFrame([{"Driver": "Lando Norris", "Qualifying": 3, "Race": 1, "Delta": 2}])
    fastest = pd.DataFrame([{"Driver": "Lando Norris", "Fastest Lap": "1:20.000"}])
    pits = pd.DataFrame([{"Driver": "landonorris", "Lap": 20, "Stop": 1, "Time": "2.4"}, {"Driver": "landonorris", "Lap": 40, "Stop": 2, "Time": "2.3"}])
    with patch("utils.data_utils.get_driver_standings", return_value=drivers), patch("utils.data_utils.get_constructor_standings", return_value=constructors), patch("utils.data_utils.get_driver_points_by_race", return_value=progression), patch("utils.data_utils.get_qualifying_vs_race_delta", return_value=qualifying), patch("utils.data_utils.get_fastest_lap_times", return_value=fastest), patch("utils.data_utils.get_pit_stop_data", return_value=pits):
        result = build_f1_dashboard("2026")
    assert result["driver_standings"][0]["driver"] == "Lando Norris"
    assert result["progression"][1]["points"]["Lando Norris"] == 43
    assert result["qualifying_vs_race"][0]["delta"] == 2
    assert result["average_stops"] == 2


def test_f1_dashboard_keeps_empty_contract_when_provider_has_no_data():
    empty = pd.DataFrame()
    with patch("utils.data_utils.get_driver_standings", return_value=empty), patch("utils.data_utils.get_constructor_standings", return_value=empty), patch("utils.data_utils.get_driver_points_by_race", return_value=empty), patch("utils.data_utils.get_qualifying_vs_race_delta", return_value=empty), patch("utils.data_utils.get_fastest_lap_times", return_value=empty), patch("utils.data_utils.get_pit_stop_data", return_value=empty):
        result = build_f1_dashboard("1950")
    assert result["driver_standings"] == []
    assert result["progression"] == []
    assert result["average_stops"] is None
