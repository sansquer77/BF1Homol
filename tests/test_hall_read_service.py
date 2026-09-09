from services.hall_read_service import assemble_hall


def test_hall_groups_seasons_winners_and_distribution_without_fabricating_champion():
    result = assemble_hall([
        {"temporada": "2025", "position": 1, "pontos": 100, "nome": "Ana"},
        {"temporada": "2025", "position": 2, "pontos": 90, "nome": "Beto"},
        {"temporada": "2024", "position": 1, "pontos": 80, "nome": "Ana"},
        {"temporada": "2023", "position": 2, "pontos": 70, "nome": "Caio"},
    ], "hall_da_fama")

    assert result["seasons"] == ["2025", "2024", "2023"]
    assert result["top_winners"][0] == {"participant": "Ana", "wins": 2}
    assert result["season_stats"][0]["champion"]["participant"] == "Ana"
    assert result["season_stats"][2]["champion"] is None
    ana = next(item for item in result["distribution"] if item["participant"] == "Ana")
    assert ana["positions"] == [{"position": 1, "count": 2}]
    assert any(item["participant"] == "Caio" for item in result["distribution"])


def test_empty_hall_has_stable_contract():
    result = assemble_hall([], "hall_da_fama")
    assert result == {"source": "hall_da_fama", "seasons": [], "entries": [], "top_winners": [], "season_stats": [], "distribution": []}
