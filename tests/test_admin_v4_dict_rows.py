from contextlib import contextmanager
import sys
import types
from unittest.mock import MagicMock, patch

from services.access_control import AuthenticatedContext
from services.admin_v4_service import list_admin_drivers, list_admin_races, list_admin_users
from services.financial_v4_service import get_financial


MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())


@contextmanager
def connection_with(rows, first=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.fetchone.return_value = first
    connection = MagicMock()
    connection.cursor.return_value = cursor
    yield connection


def database_modules(connect):
    package = types.ModuleType("db")
    package.__path__ = []
    schema = types.ModuleType("db.db_schema")
    schema.db_connect = connect
    return {"db": package, "db.db_schema": schema}


def test_admin_catalog_reads_psycopg_dict_rows():
    cases = [
        (list_admin_users, (), [{"id": 2, "nome": "Ana", "email": "a@example.com", "perfil": "admin", "status": "Ativo", "must_change_password": False}], "name", "Ana"),
        (list_admin_drivers, (), [{"id": 3, "nome": "Lando", "equipe": "McLaren", "status": "Ativo", "numero": 4}], "team", "McLaren"),
        (list_admin_races, ("2026",), [{"id": 4, "nome": "GP A", "data": "2026-01-01", "horario_prova": "10:00", "tipo": "Normal", "status": "Pendente", "circuit_id": "test"}], "race_status", "Pendente"),
    ]
    for action, args, rows, field, expected in cases:
        connect = MagicMock(return_value=connection_with(rows))
        with patch.dict(sys.modules, database_modules(connect)):
            assert action(MASTER, *args)[0][field] == expected


def test_financial_reads_psycopg_dict_rows():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"valor_taxa": 200}
    cursor.fetchall.return_value = [{"id": 2, "nome": "Ana", "email": "a@example.com", "pago": True}]
    connection = MagicMock(); connection.cursor.return_value = cursor
    @contextmanager
    def connect():
        yield connection
    with patch.dict(sys.modules, database_modules(connect)):
        result = get_financial(MASTER, "2026")
    assert result["fee"] == 200.0
    assert result["participants"] == [{"user_id": 2, "name": "Ana", "email": "a@example.com", "paid": True}]
