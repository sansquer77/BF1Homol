from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.financial_v4_service import get_financial, save_financial, send_financial_reminder

MASTER = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset({"2026"}))


def _connection(*, fee=200, payments=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = {"valor_taxa": fee}
    cursor.fetchall.return_value = payments or []
    connection = MagicMock()
    connection.cursor.return_value = cursor

    @contextmanager
    def connect():
        yield connection
    return connect, connection


def test_financial_uses_historical_participants_excludes_master_and_calculates_fund():
    connect, _ = _connection(payments=[{"usuario_id": 2, "pago": True}])
    frame = pd.DataFrame([
        {"id": 1, "nome": "Master", "email": "master@example.com", "perfil": "master"},
        {"id": 3, "nome": "Bia", "email": "bia@example.com", "perfil": "participante"},
        {"id": 2, "nome": "Ana", "email": "ana@example.com", "perfil": "participante"},
    ])
    with patch("db.db_schema.db_connect", connect), patch("db.repo_bets.get_participantes_temporada_df", return_value=frame):
        result = get_financial(MASTER, "2026")
    assert [item["name"] for item in result["participants"]] == ["Ana", "Bia"]
    assert result["summary"] == {"participants_total": 2, "paid_total": 1, "pending_total": 1, "collected": 200.0, "outstanding": 200.0, "total_due": 400.0}
    assert result["prizes"] == {"winner": 160.0, "runner_up": 120.0, "third": 80.0, "administration": 40.0}


def test_financial_write_keeps_legacy_tables_and_is_master_only():
    with pytest.raises(AuthorizationDenied):
        save_financial(ADMIN, "2026", 200, {2: True})
    connect, connection = _connection()
    with patch("db.db_schema.db_connect", connect):
        save_financial(MASTER, "2026", 200, {2: True, 3: False})
    sql = " ".join(call.args[0] for call in connection.cursor.return_value.execute.call_args_list)
    assert "financeiro_config_temporada" in sql
    assert "financeiro_participantes" in sql
    connection.commit.assert_called_once()


def test_reminder_derives_only_pending_valid_emails_and_records_count():
    financial = {"participants": [
        {"email": "pago@example.com", "paid": True},
        {"email": "Pendente@Example.com", "paid": False},
        {"email": "invalido", "paid": False},
    ]}
    send = MagicMock(return_value=True)
    record = MagicMock()
    with patch("services.financial_v4_service.get_financial", return_value=financial), patch("services.email_service.enviar_email", send), patch("db.repo_observability.record_event", record):
        assert send_financial_reminder(MASTER, "2026") == 1
    assert send.call_args.kwargs["cco"] == ["pendente@example.com"]
    assert record.call_args.kwargs["metadata"] == {"season": "2026", "recipient_count": 1}


def test_financial_read_and_reminder_are_master_only():
    with pytest.raises(AuthorizationDenied):
        get_financial(ADMIN, "2026")
    with pytest.raises(AuthorizationDenied):
        send_financial_reminder(ADMIN, "2026")
