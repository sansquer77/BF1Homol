from contextlib import contextmanager
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_v4_service import list_admin_drivers, list_admin_races, list_admin_users, update_user, upsert_driver, upsert_race
from services.financial_v4_service import get_financial


MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset({"2026"}))


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


def test_only_master_can_edit_users_drivers_and_races():
    with pytest.raises(AuthorizationDenied):
        update_user(ADMIN, 7, {"nome": "Novo nome"})
    with pytest.raises(AuthorizationDenied):
        upsert_driver(ADMIN, 8, {"nome": "Piloto"})
    with pytest.raises(AuthorizationDenied):
        upsert_race(ADMIN, 9, "2026", {"nome": "Prova"})


def test_master_edit_calls_existing_repositories():
    users = types.ModuleType("db.repo_users"); users.update_usuario = MagicMock(return_value=True)
    races = types.ModuleType("db.repo_races")
    races.update_piloto = MagicMock(return_value=True); races.add_piloto = MagicMock()
    races.update_prova = MagicMock(return_value=True); races.add_prova = MagicMock()
    with patch.dict(sys.modules, {"db.repo_users": users, "db.repo_races": races}):
        update_user(MASTER, 7, {"nome": "Ana", "email": "ana@example.com"})
        upsert_driver(MASTER, 8, {"nome": "Lando", "equipe": "McLaren", "status": "Ativo", "numero": 4})
        upsert_race(MASTER, 9, "2026", {"nome": "GP", "data": "2026-01-01", "horario_prova": "10:00", "tipo": "Normal", "status": "Pendente"})
    users.update_usuario.assert_called_once_with(7, nome="Ana", email="ana@example.com")
    races.update_piloto.assert_called_once()
    races.update_prova.assert_called_once()


def test_financial_reads_psycopg_dict_rows():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"valor_taxa": 200}
    cursor.fetchall.return_value = [{"usuario_id": 2, "pago": True}]
    connection = MagicMock(); connection.cursor.return_value = cursor
    @contextmanager
    def connect():
        yield connection
    modules = database_modules(connect)
    bets = types.ModuleType("db.repo_bets")
    bets.get_participantes_temporada_df = MagicMock(return_value=pd.DataFrame([{"id": 2, "nome": "Ana", "email": "a@example.com", "perfil": "participante"}]))
    modules["db.repo_bets"] = bets
    with patch.dict(sys.modules, modules):
        result = get_financial(MASTER, "2026")
    assert result["fee"] == 200.0
    assert result["participants"] == [{"user_id": 2, "name": "Ana", "email": "a@example.com", "paid": True}]
    assert result["summary"]["collected"] == 200.0
