from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.account_v4_service import change_own_email, change_own_password
from services.participant_panel_v4_service import build_personal_bets, build_personal_history


PARTICIPANT = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))


def test_personal_bets_filters_authenticated_user_and_reports_discard():
    bets = pd.DataFrame([
        {"usuario_id": 7, "prova_id": 10, "nome_prova": "GP A", "pilotos_arr": ["Piloto A", "Piloto B"], "fichas_arr": [5, 2], "piloto_11": "Piloto C", "automatica": 0},
        {"usuario_id": 8, "prova_id": 10, "nome_prova": "GP A", "pilotos": "Outro", "fichas": "1", "piloto_11": "Piloto C"},
        {"usuario_id": 7, "prova_id": 20, "nome_prova": "GP B", "pilotos": "Piloto A, Piloto D", "fichas": "3,4", "piloto_11": "Piloto E", "automatica": 1},
    ])
    races = pd.DataFrame([{"id": 10, "nome": "GP A", "tipo": "Normal"}, {"id": 20, "nome": "GP B", "tipo": "Sprint"}])
    results = pd.DataFrame([{"prova_id": 10, "posicoes": "{1: 'Piloto A', 11: 'Piloto C'}"}, {"prova_id": 20, "posicoes": "{2: 'Piloto D', 11: 'Piloto X'}"}])
    patches = (
        patch("db.repo_bets.get_apostas_df", return_value=bets),
        patch("db.repo_races.get_provas_df", return_value=races),
        patch("db.repo_races.get_resultados_df", return_value=results),
        patch("services.bets_scoring.calcular_pontuacao_lote", return_value=[120.0, 85.0]),
        patch("services.rules_service.get_regras_aplicaveis", return_value={"descarte": True}),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        snapshot = build_personal_bets(7, "2026")

    assert [item["race_name"] for item in snapshot["entries"]] == ["GP A", "GP B"]
    assert snapshot["entries"][0]["allocations"][0] == {"driver": "Piloto A", "chips": 5, "actual_position": 1, "points_contribution": 125.0}
    assert snapshot["entries"][0]["eleventh_actual"] == "Piloto C"
    assert snapshot["discard_active"] is True
    assert snapshot["discard_race"] == "GP B"
    assert snapshot["discard_points"] == 85.0


def test_personal_history_uses_hall_and_registered_seasons():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"temporada": "2024", "position": 2, "pontos": 3010},
        {"temporada": "2025", "position": 1, "pontos": 3200},
    ]
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value = cursor
    graph = SimpleNamespace(fichas_por_temporada_piloto={"2023": {"Piloto C": 8}, "2024": {"Piloto A": 15}, "2025": {"Piloto B": 20}})
    with patch("db.db_schema.db_connect", return_value=connection), patch("services.hall_da_fama_controller.resolve_hall_source", return_value=("hall_da_fama", None)), patch("services.historico_service.calcular_dados_grafico", return_value=graph):
        snapshot = build_personal_history(7)

    assert snapshot["seasons_count"] == 2
    assert snapshot["best_position"] == 1
    assert snapshot["titles"] == 1
    assert snapshot["podiums"] == 2
    assert snapshot["best_points"] == 3200.0
    assert snapshot["series"][0]["season"] == "2024"
    assert [item["season"] for item in snapshot["series"]] == ["2024", "2025"]


def test_account_changes_require_current_password_and_reject_master():
    user = {"id": 7, "email": "ana@example.com", "perfil": "participante", "senha_hash": "hash"}
    with patch("db.repo_users.get_user_by_id", return_value=user), patch("db.repo_users.check_password", side_effect=lambda plain, _: plain == "Atual1Senha"), patch("db.repo_users.get_user_by_email", return_value=None), patch("db.repo_users.update_user_email", return_value=True) as update:
        changed = change_own_email(PARTICIPANT, "Atual1Senha", "Nova@Example.com")
    assert changed["email"] == "nova@example.com"
    update.assert_called_once_with(7, "nova@example.com")

    with patch("db.repo_users.get_user_by_id", return_value=user), patch("db.repo_users.check_password", return_value=False):
        with pytest.raises(AuthorizationDenied):
            change_own_email(PARTICIPANT, "errada", "nova@example.com")

    master = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
    master_user = {"id": 1, "perfil": "master", "senha_hash": "hash"}
    with patch("db.repo_users.get_user_by_id", return_value=master_user), patch("db.repo_users.check_password") as check:
        with pytest.raises(ValueError, match="variáveis de ambiente"):
            change_own_password(master, "Atual1Senha", "Nova2Senha")
    check.assert_not_called()


def test_account_password_validates_current_password_and_policy():
    user = {"id": 7, "email": "ana@example.com", "perfil": "participante", "senha_hash": "hash"}
    with patch("db.repo_users.get_user_by_id", return_value=user), patch("db.repo_users.check_password", side_effect=[True, False]), patch("db.repo_users.update_user_password", return_value=True) as update:
        change_own_password(PARTICIPANT, "Atual1Senha", "Nova2Senha")
    update.assert_called_once_with(7, "Nova2Senha")
