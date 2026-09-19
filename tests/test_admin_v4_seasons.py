from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_v4_service import create_admin_season, list_admin_seasons


MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())


@contextmanager
def fake_connection(rows=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    yield connection


def test_master_creates_explicit_season_and_invalidates_dependent_caches():
    connection = fake_connection(rows=[{"temporada": "2025"}, {"temporada": "2026"}])
    with patch("db.db_schema.db_connect", return_value=connection), patch(
        "services.admin_v4_service.clear_data_cache"
    ) as clear:
        result = create_admin_season(MASTER)

    assert result == {"season": "2027", "created": True}
    clear.assert_any_call("calendario")
    clear.assert_any_call("telemetria")


def test_admin_can_list_but_cannot_create_season():
    connection = fake_connection(rows=[{"temporada": "2026", "criado_em": None}])
    with patch("db.db_schema.db_connect", return_value=connection):
        assert list_admin_seasons(ADMIN) == [{"season": "2026", "created_at": None}]
    with pytest.raises(AuthorizationDenied):
        create_admin_season(ADMIN)
