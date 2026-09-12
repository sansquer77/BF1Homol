from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

from services.telemetry_service import build_telemetry_snapshot


def test_snapshot_uses_authenticated_user_and_materialized_v3_data():
    races = pd.DataFrame([
        {"id": 10, "nome": "GP Passado", "data": "2026-08-01", "horario_prova": "10:00", "tipo": "Normal", "circuit_id": "interlagos"},
        {"id": 20, "nome": "GP Futuro", "data": "2026-10-01", "horario_prova": "11:00", "tipo": "Sprint", "circuit_id": "baku"},
    ])
    bets = pd.DataFrame([
        {"usuario_id": 7, "prova_id": 10},
        {"usuario_id": 8, "prova_id": 10},
    ])
    positions = pd.DataFrame([
        {"usuario_id": 7, "prova_id": 10, "posicao": 2, "pontos": 18},
        {"usuario_id": 8, "prova_id": 10, "posicao": 1, "pontos": 25},
    ])
    users = pd.DataFrame([{"id": 7, "nome": "Ana"}, {"id": 8, "nome": "Beto"}])
    with patch("db.repo_races.get_provas_df", return_value=races), \
         patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_bets.get_posicoes_participantes_df", return_value=positions), \
         patch("db.repo_bets.get_participantes_temporada_df", return_value=users), \
         patch("db.circuitos_utils.get_circuit_coordinates", return_value=None):
        snapshot = build_telemetry_snapshot(
            7, "Ana", "2026", now=datetime(2026, 9, 8, tzinfo=ZoneInfo("America/Sao_Paulo"))
        )

    assert snapshot["user_name"] == "Ana"
    assert snapshot["next_race"]["id"] == 20
    assert snapshot["next_race"]["circuit_id"] == "baku"
    assert snapshot["next_race"]["weather"]["available"] is False
    assert snapshot["metrics"] == {"current_position": 2, "points": 18.0, "bets_submitted": 1, "races_total": 2}
    assert snapshot["evolution"][0]["cumulative_points"] == 18.0
    assert snapshot["ranking"][0]["name"] == "Beto"
    assert "email" not in snapshot["ranking"][0]


def test_snapshot_returns_valid_empty_contract():
    empty = pd.DataFrame()
    with patch("db.repo_races.get_provas_df", return_value=empty), \
         patch("db.repo_bets.get_apostas_df", return_value=empty), \
         patch("db.repo_bets.get_posicoes_participantes_df", return_value=empty), \
         patch("db.repo_bets.get_participantes_temporada_df", return_value=empty):
        snapshot = build_telemetry_snapshot(7, "Ana", "2026")

    assert snapshot["next_race"] is None
    assert snapshot["metrics"] == {"current_position": None, "points": 0, "bets_submitted": 0, "races_total": 0}
    assert snapshot["evolution"] == []
    assert snapshot["ranking"] == []
