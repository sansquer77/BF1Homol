from datetime import datetime
from unittest.mock import patch

from services.access_control import AuthenticatedContext
from services.championship_v4_service import place_championship_bet


def test_championship_bet_rejects_same_champion_and_vice_before_persistence():
    context = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))
    with patch("services.championship_v4_service.db_connect", create=True) as connect:
        try:
            place_championship_bet(2026, "Lando Norris", "Lando Norris", "McLaren", context)
        except ValueError as exc:
            assert "diferentes" in str(exc)
        else:
            raise AssertionError("Aposta inválida deveria ser rejeitada")
        connect.assert_not_called()


def test_championship_bet_delegates_deadline_and_uses_authenticated_user():
    context = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))
    fake_user = {"id": 7, "nome": "Ana", "status": "ativo"}
    with patch("services.championship_v4_service.can_place_championship_bet", return_value=(False, "encerrada", datetime(2026, 1, 1))), patch("services.championship_v4_service.get_user_by_id", return_value=fake_user, create=True), patch("services.championship_v4_service.db_connect", create=True) as connect:
        try:
            place_championship_bet(2026, "Lando Norris", "Max Verstappen", "McLaren", context)
        except ValueError as exc:
            assert str(exc) == "encerrada"
        else:
            raise AssertionError("Deadline deveria bloquear a aposta")
        connect.assert_not_called()
