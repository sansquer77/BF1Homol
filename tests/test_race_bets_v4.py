from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

from services.access_control import AuthenticatedContext
from services.race_bets_v4_service import build_race_bet_snapshot, place_race_bet


CONTEXT = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))
RULES = {"quantidade_fichas": 3, "fichas_por_piloto": 2, "qtd_minima_pilotos": 2, "mesma_equipe": False}


def test_snapshot_uses_session_user_and_active_rules():
    races = pd.DataFrame([{"id": 10, "nome": "GP Teste", "data": "2026-12-01", "horario_prova": "10:00", "tipo": "Normal"}])
    drivers = pd.DataFrame([{"nome": "A", "equipe": "Ferrari", "status": "Ativo"}, {"nome": "B", "equipe": "McLaren", "status": "Ativo"}, {"nome": "C", "equipe": "Alpine", "status": "Ativo"}, {"nome": "Inativo", "equipe": "Haas", "status": "Inativo"}])
    stored = {"pilotos": "A,B", "fichas": "2,1", "piloto_11": "C", "data_envio": "2026-11-01T10:00:00-03:00"}
    with patch("db.repo_races.get_provas_df", return_value=races), patch("db.repo_races.get_resultados_df", return_value=pd.DataFrame()), patch("db.repo_races.get_pilotos_df", return_value=drivers), patch("db.repo_bets.get_aposta", return_value=stored), patch("services.race_bets_v4_service.get_regras_aplicaveis", return_value=RULES), patch("services.race_bets_v4_service.pode_fazer_aposta", return_value=(True, "Aposta permitida", datetime(2026, 12, 1, 10, tzinfo=ZoneInfo("America/Sao_Paulo")))):
        snapshot = build_race_bet_snapshot("2026", CONTEXT)
    assert snapshot["selected_race"]["id"] == 10
    assert snapshot["rules"]["total_chips"] == 3
    assert [driver["name"] for driver in snapshot["drivers"]] == ["A", "B", "C"]
    assert snapshot["current_bet"]["allocations"] == [{"driver": "A", "chips": 2}, {"driver": "B", "chips": 1}]


def test_submission_reuses_legacy_validation_and_authenticated_user():
    snapshot = {"selected_race": {"id": 10, "name": "GP Teste", "type": "Normal", "is_open": True}, "drivers": [{"name": "A", "team": "Ferrari"}, {"name": "B", "team": "McLaren"}, {"name": "C", "team": "Alpine"}]}
    with patch("services.race_bets_v4_service.build_race_bet_snapshot", return_value=snapshot), patch("services.race_bets_v4_service.get_regras_aplicaveis", return_value=RULES), patch("services.bets_write.salvar_aposta", return_value=True) as save:
        result = place_race_bet("2026", 10, [{"driver": "A", "chips": 2}, {"driver": "B", "chips": 1}], "C", CONTEXT)
    assert result["status"] == "registered"
    assert save.call_args.args[0] == 7
    assert save.call_args.kwargs["temporada"] == "2026"


def test_submission_rejects_duplicate_team_before_write():
    snapshot = {"selected_race": {"id": 10, "name": "GP Teste", "type": "Normal", "is_open": True}, "drivers": [{"name": "A", "team": "Ferrari"}, {"name": "B", "team": "Ferrari"}, {"name": "C", "team": "Alpine"}]}
    with patch("services.race_bets_v4_service.build_race_bet_snapshot", return_value=snapshot), patch("services.race_bets_v4_service.get_regras_aplicaveis", return_value=RULES), patch("services.bets_write.salvar_aposta") as save:
        try:
            place_race_bet("2026", 10, [{"driver": "A", "chips": 2}, {"driver": "B", "chips": 1}], "C", CONTEXT)
        except ValueError as exc:
            assert "regras vigentes" in str(exc)
        else:
            raise AssertionError("Aposta inválida deveria ser recusada")
    save.assert_not_called()


def test_submission_rejects_eleventh_driver_also_in_allocations():
    snapshot = {"selected_race": {"id": 10, "name": "GP Teste", "type": "Normal", "is_open": True}, "drivers": [{"name": "A", "team": "Ferrari"}, {"name": "B", "team": "McLaren"}, {"name": "C", "team": "Alpine"}]}
    with patch("services.race_bets_v4_service.build_race_bet_snapshot", return_value=snapshot), patch("services.race_bets_v4_service.get_regras_aplicaveis", return_value=RULES), patch("services.bets_write.salvar_aposta") as save:
        try:
            place_race_bet("2026", 10, [{"driver": "A", "chips": 2}, {"driver": "B", "chips": 1}], "A", CONTEXT)
        except ValueError as exc:
            assert "regras vigentes" in str(exc)
        else:
            raise AssertionError("Piloto do 11º também apostado deveria ser recusado")
    save.assert_not_called()
