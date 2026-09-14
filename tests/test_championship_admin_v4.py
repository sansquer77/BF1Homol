from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api.schemas import ChampionshipAdminResponse, ChampionshipResponse
from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.championship_v4_service import build_championship_admin_snapshot, save_official_result

MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())
PARTICIPANT = AuthenticatedContext(3, "Bia", "participante", "ativo", frozenset({"2026"}))


def _connection(fetches):
    cursor = MagicMock()
    cursor.fetchall.side_effect = fetches
    connection = MagicMock()
    connection.cursor.return_value = cursor

    @contextmanager
    def connect():
        yield connection
    return connect, connection


def test_admin_snapshot_tracks_completion_pending_distributions_and_history():
    participants = pd.DataFrame([
        {"id": 1, "nome": "Master", "perfil": "master"},
        {"id": 2, "nome": "Admin", "perfil": "admin"},
        {"id": 3, "nome": "Bia", "perfil": "participante"},
        {"id": 4, "nome": "Caio", "perfil": "participante"},
    ])
    bets = [
        {"user_id": 2, "user_nome": "Admin", "champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": 2026, "bet_time": datetime(2026, 2, 1, 10)},
        {"user_id": 3, "user_nome": "Bia", "champion": "Lando", "vice": "Charles", "team": "Ferrari", "season": 2026, "bet_time": datetime(2026, 2, 2, 10)},
    ]
    history = bets + [{**bets[1], "champion": "Charles", "bet_time": datetime(2026, 1, 20, 10)}]
    connect, _ = _connection([bets, history])
    base = {"official_result": None, "drivers": ["Lando", "Oscar"], "teams": ["McLaren"], "can_bet": True, "deadline_message": "aberta", "deadline": None}
    with patch("services.championship_v4_service.build_championship_snapshot", return_value=base), patch("db.repo_bets.get_participantes_temporada_df", return_value=participants), patch("db.db_schema.db_connect", connect):
        result = build_championship_admin_snapshot(2026, ADMIN)
    assert result["eligible_count"] == 3
    assert result["bet_count"] == 2
    assert result["pending"] == [{"user_id": 4, "name": "Caio"}]
    assert result["completion_percent"] == 66.7
    assert result["champion_distribution"][0] == {"label": "Lando", "count": 2}
    assert len(result["history"]) == 3
    assert result["bets"][0]["bet_time"] == "2026-02-01T10:00:00"


def test_participant_cannot_read_administrative_tracking():
    with pytest.raises(AuthorizationDenied):
        build_championship_admin_snapshot(2026, PARTICIPANT)


def test_official_result_invalidates_championship_and_classification_caches():
    connect, connection = _connection([])
    with patch("db.db_schema.db_connect", connect), patch("utils.cache_utils.clear_data_cache") as clear:
        result = save_official_result(2026, "Lando", "Oscar", "McLaren", MASTER)
    assert result["champion"] == "Lando"
    connection.commit.assert_called_once()
    clear.assert_called_once_with("championship", "classificacao")


def test_championship_response_schema_coerces_datetime_bet_time():
    payload = {
        "season": "2026",
        "drivers": [],
        "teams": [],
        "current_bet": {"champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": "2026", "bet_time": datetime(2026, 2, 23, 15, 0, 59)},
        "history": [{"user_nome": "Admin", "champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": "2026", "bet_time": datetime(2026, 2, 23, 15, 0, 59)}],
        "all_bets": [{"user_id": 1, "user_nome": "Admin", "champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": "2026", "bet_time": datetime(2026, 2, 23, 15, 0, 59)}],
        "official_result": None,
        "can_bet": True,
        "deadline_message": "aberta",
        "deadline": None,
    }
    response = ChampionshipResponse.model_validate(payload)
    assert response.current_bet.bet_time == "2026-02-23T15:00:59"
    assert response.history[0].bet_time == "2026-02-23T15:00:59"
    assert response.all_bets[0].bet_time == "2026-02-23T15:00:59"


def test_championship_admin_response_schema_coerces_datetime_bet_time():
    payload = {
        "season": "2026",
        "eligible_count": 1,
        "bet_count": 1,
        "pending_count": 0,
        "completion_percent": 100.0,
        "pending": [],
        "bets": [{"user_id": 1, "user_nome": "Admin", "champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": "2026", "bet_time": datetime(2026, 2, 23, 15, 0, 59)}],
        "history": [{"user_id": 1, "user_nome": "Admin", "champion": "Lando", "vice": "Oscar", "team": "McLaren", "season": "2026", "bet_time": datetime(2026, 2, 23, 15, 0, 59)}],
        "champion_distribution": [],
        "vice_distribution": [],
        "team_distribution": [],
        "official_result": None,
        "drivers": [],
        "teams": [],
        "can_bet": True,
        "deadline_message": "aberta",
        "deadline": None,
    }
    response = ChampionshipAdminResponse.model_validate(payload)
    assert response.bets[0].bet_time == "2026-02-23T15:00:59"
    assert response.history[0].bet_time == "2026-02-23T15:00:59"
