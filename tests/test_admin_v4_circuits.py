import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_v4_service import list_admin_circuits, refresh_admin_circuits


MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())
PARTICIPANT = AuthenticatedContext(3, "Participante", "participante", "ativo", frozenset({"2026"}))


class FakeFrame:
    def to_dict(self, orient):
        assert orient == "records"
        return [{"circuit_id": "interlagos", "circuit_name": "Interlagos", "country": "Brazil", "locality": "São Paulo"}]


def circuit_module(**overrides):
    package = types.ModuleType("db")
    package.__path__ = []
    module = types.ModuleType("db.circuitos_utils")
    module.get_circuitos_df = overrides.get("get_circuitos_df", lambda: FakeFrame())
    module.get_temporadas_existentes_provas = overrides.get("get_temporadas_existentes_provas", lambda: ["2025"])
    module.atualizar_base_circuitos = overrides.get("atualizar_base_circuitos", lambda seasons: {"temporadas": len(seasons), "circuitos": 1})
    return {"db": package, "db.circuitos_utils": module}


def test_admin_and_master_list_canonical_circuit_options():
    with patch.dict(sys.modules, circuit_module()):
        assert list_admin_circuits(ADMIN) == [{"circuit_id": "interlagos", "circuit_name": "Interlagos", "country": "Brazil", "locality": "São Paulo"}]
        assert list_admin_circuits(MASTER)[0]["circuit_id"] == "interlagos"


def test_refresh_uses_existing_selected_and_previous_seasons():
    updater = MagicMock(return_value={"temporadas": 3, "circuitos": 24})
    modules = circuit_module(get_temporadas_existentes_provas=lambda: ["2024"], atualizar_base_circuitos=updater)
    with patch.dict(sys.modules, modules):
        assert refresh_admin_circuits(ADMIN, "2026") == {"temporadas": 3, "circuitos": 24}
    updater.assert_called_once_with(["2024", "2025", "2026"])


def test_participant_cannot_read_or_refresh_circuit_catalog():
    with pytest.raises(AuthorizationDenied):
        list_admin_circuits(PARTICIPANT)
    with pytest.raises(AuthorizationDenied):
        refresh_admin_circuits(PARTICIPANT, "2026")
