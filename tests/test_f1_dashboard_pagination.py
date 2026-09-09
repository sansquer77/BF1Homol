from unittest.mock import patch

from utils.data_utils import get_driver_points_by_race


def _page(offset: int):
    races = {
        0: [{"round": "1", "raceName": "GP A", "Results": [{"Driver": {"driverId": "ana", "givenName": "Ana", "familyName": "Silva"}, "points": "10"}, {"Driver": {"driverId": "beto", "givenName": "Beto", "familyName": "Souza"}, "points": "8"}]}],
        2: [{"round": "2", "raceName": "GP B", "Results": [{"Driver": {"driverId": "ana", "givenName": "Ana", "familyName": "Silva"}, "points": "7.5"}, {"Driver": {"driverId": "beto", "givenName": "Beto", "familyName": "Souza"}, "points": "6"}]}],
    }
    return {"MRData": {"total": "4", "limit": "2", "RaceTable": {"Races": races[offset]}}}


def test_progression_fetches_all_result_pages_and_preserves_fractional_points():
    def request(url: str):
        return _page(2 if "offset=2" in url else 0)

    with patch("utils.data_utils._request_json", side_effect=request):
        result = get_driver_points_by_race("2098")

    assert result["Race"].tolist() == ["GP A", "GP B"]
    assert result["Ana Silva"].tolist() == [10.0, 17.5]
    assert result["Beto Souza"].tolist() == [8.0, 14.0]
