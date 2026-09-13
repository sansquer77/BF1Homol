from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.results_admin_v4_service import get_result_management, save_and_process_result

MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset({"2026"}))
PARTICIPANT = AuthenticatedContext(3, "Ana", "participante", "ativo", frozenset({"2026"}))


def _snapshot():
    return {
        "season": "2026", "selected_race_id": 10,
        "drivers": [{"id": index, "name": f"Piloto {index}", "team": "Equipe"} for index in range(1, 13)],
        "races": [{"id": 10, "name": "GP Teste", "date": "2026-09-10", "time": "10:00", "type": "Normal", "has_result": False, "positions": {}, "retirements": []}],
    }


def test_management_prefills_existing_result_and_filters_active_drivers():
    races = pd.DataFrame([{"id": 10, "nome": "GP", "data": "2026-09-10", "horario_prova": "10:00", "tipo": "Normal"}])
    drivers = pd.DataFrame([{"id": 1, "nome": "Ativo", "equipe": "Ferrari", "status": "Ativo"}, {"id": 2, "nome": "Fora", "equipe": "Haas", "status": "Inativo"}])
    results = pd.DataFrame([{"prova_id": 10, "posicoes": "{1: 'Ativo'}", "abandono_pilotos": "Fora"}])
    with patch("db.repo_races.get_provas_df", return_value=races), patch("db.repo_races.get_pilotos_df", return_value=drivers), patch("db.repo_races.get_resultados_df", return_value=results), patch("services.results_admin_v4_service.get_prova_atual_sem_resultado_id", return_value=None):
        result = get_result_management(ADMIN, "2026")
    assert result["drivers"] == [{"id": 1, "name": "Ativo", "team": "Ferrari"}]
    assert result["races"][0]["positions"] == {"1": "Ativo"}
    assert result["races"][0]["has_result"] is True


def test_save_processes_scoring_and_keeps_email_failure_non_fatal():
    positions = {str(index): f"Piloto {index}" for index in range(1, 12)}
    save = patch("services.admin_operations.admin_save_resultado")
    score = patch("services.bets_scoring.atualizar_classificacoes_todas_as_provas")
    notify = patch("services.result_notification_service.enviar_emails_resultado_prova", return_value=SimpleNamespace(enviados=8, falhas=1, sem_aposta=2))
    with patch("services.results_admin_v4_service.get_result_management", return_value=_snapshot()), save as persist, score as recalculate, notify:
        result = save_and_process_result(ADMIN, 10, "2026", positions, ["Piloto 12"])
    persist.assert_called_once()
    recalculate.assert_called_once_with("2026")
    assert result["status"] == "processed"
    assert result["notifications"]["sent"] == 8
    assert result["notifications"]["warning"]


def test_result_rejects_invalid_positions_and_unauthorized_profile():
    with pytest.raises(AuthorizationDenied):
        get_result_management(PARTICIPANT, "2026")
    with patch("services.results_admin_v4_service.get_result_management", return_value=_snapshot()):
        with pytest.raises(ValueError, match="Preencha"):
            save_and_process_result(MASTER, 10, "2026", {"1": "Piloto 1"}, [])
