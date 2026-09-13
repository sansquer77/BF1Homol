from unittest.mock import patch

import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_v4_service import list_admin_teams, upsert_team
from api.routes.teams import teams

MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())


def test_team_catalog_maps_legacy_repository_fields_for_admin():
    rows = [{"id": 1, "nome": "Alpine", "cor_primaria": "#005BA9", "cor_secundaria": "#FF80BD", "status": "Ativa"}]
    with patch("db.equipes_utils.list_equipes", return_value=rows):
        assert list_admin_teams(ADMIN) == [{"id": 1, "name": "Alpine", "primary_color": "#005BA9", "secondary_color": "#FF80BD", "status": "Ativa"}]


def test_only_master_can_write_team_and_colors_are_validated():
    with pytest.raises(AuthorizationDenied):
        upsert_team(ADMIN, None, {"name": "Ferrari", "primary_color": "#DC0000"})
    with pytest.raises(ValueError):
        upsert_team(MASTER, None, {"name": "Ferrari", "primary_color": "red"})
    with patch("db.equipes_utils.save_equipe", return_value=4) as save:
        assert upsert_team(MASTER, None, {"name": " Ferrari ", "primary_color": "#dc0000", "status": "Ativa"}) == 4
    save.assert_called_once_with(None, name="Ferrari", primary_color="#DC0000", secondary_color=None, status="Ativa")


def test_authenticated_palette_maps_database_fields_to_api_contract():
    rows = [{"id": 7, "nome": "Haas", "cor_primaria": "#9C9FA2", "cor_secundaria": "#EB0A1E", "status": "Ativa"}]
    with patch("db.equipes_utils.list_equipes", return_value=rows):
        assert teams(ADMIN)[0].model_dump() == {
            "id": 7, "name": "Haas", "primary_color": "#9C9FA2",
            "secondary_color": "#EB0A1E", "status": "Ativa",
        }
