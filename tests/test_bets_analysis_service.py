from unittest.mock import patch

import pandas as pd

from services.bets_analysis_service import build_bets_analysis


def test_analysis_limits_participant_and_aggregates_drivers_and_chips():
    bets = pd.DataFrame([
        {"usuario_id": 7, "prova_id": 1, "pilotos": "A,B", "fichas": "10,5", "piloto_11": "C"},
        {"usuario_id": 8, "prova_id": 1, "pilotos": "C", "fichas": "15", "piloto_11": "A"},
    ])
    drivers = pd.DataFrame([{"nome": "A", "equipe": "Ferrari"}, {"nome": "B", "equipe": "McLaren"}, {"nome": "C", "equipe": "Mercedes"}])
    with patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_races.get_pilotos_df", return_value=drivers), \
         patch("db.repo_races.get_provas_df", return_value=pd.DataFrame([{"id": 1}])), \
         patch("db.repo_races.get_resultados_df", return_value=pd.DataFrame()):
        result = build_bets_analysis("2026", scope_user_id=7)

    assert result["scope"] == "individual"
    assert result["bet_count"] == 1
    assert [(row["driver"], row["chips"]) for row in result["by_driver"]] == [("A", 10), ("B", 5)]
    assert result["eleventh"] == [{"driver": "C", "team": "Mercedes", "bets": 1}]
