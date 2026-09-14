"""Testes do serviço de alterações da própria conta na V4."""

from unittest.mock import MagicMock, patch

import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.account_v4_service import change_own_timezone


PARTICIPANT = AuthenticatedContext(3, "Bia", "participante", "ativo", frozenset({"2026"}), "America/Sao_Paulo")


def test_change_own_timezone_rejects_invalid_timezone():
    with pytest.raises(ValueError, match="Timezone inválido"):
        change_own_timezone(PARTICIPANT, "Mars/Phobos")


def test_change_own_timezone_updates_valid_timezone():
    user = {"id": 3, "nome": "Bia", "email": "bia@example.com", "perfil": "participante", "status": "ativo", "timezone": "America/Sao_Paulo"}
    with patch("db.repo_users.get_user_by_id", return_value=user), \
         patch("db.repo_users.update_user_timezone", return_value=True):
        result = change_own_timezone(PARTICIPANT, "America/New_York")
    assert result["timezone"] == "America/New_York"


def test_change_own_timezone_raises_when_update_fails():
    user = {"id": 3, "nome": "Bia", "email": "bia@example.com", "perfil": "participante", "status": "ativo"}
    with patch("db.repo_users.get_user_by_id", return_value=user), \
         patch("db.repo_users.update_user_timezone", return_value=False):
        with pytest.raises(ValueError, match="Não foi possível alterar"):
            change_own_timezone(PARTICIPANT, "America/New_York")
