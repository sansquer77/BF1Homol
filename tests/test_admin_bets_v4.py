from unittest.mock import patch

import pandas as pd
import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_bets_v4_service import generate_admin_bet, get_admin_bets, send_admin_bet_reminder


ADMIN = AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())
PARTICIPANT = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))


def _frames():
    participants = pd.DataFrame([
        {"id": 7, "nome": "Ana", "email": "ana@example.com", "perfil": "participante"},
        {"id": 8, "nome": "Beto", "email": "beto@example.com", "perfil": "participante"},
        {"id": 1, "nome": "Master", "email": "master@example.com", "perfil": "master"},
    ])
    races = pd.DataFrame([
        {"id": 10, "nome": "GP A", "data": "2026-03-01", "horario_prova": "10:00", "tipo": "Normal"},
        {"id": 20, "nome": "GP B", "data": "2026-03-08", "horario_prova": "11:00", "tipo": "Sprint"},
    ])
    bets = pd.DataFrame([
        {"usuario_id": 7, "prova_id": 10, "pilotos": "A,B", "fichas": "2,1", "piloto_11": "C", "automatica": 0, "data_envio": "2026-02-28"},
        {"usuario_id": 8, "prova_id": 10, "pilotos_arr": ["B", "C"], "fichas_arr": [2, 1], "piloto_11": "A", "automatica": 1, "data_envio": "2026-02-28"},
    ])
    return participants, races, bets


def test_snapshot_supports_race_user_and_analytical_report():
    with patch("services.admin_bets_v4_service._load_frames", return_value=_frames()):
        snapshot = get_admin_bets(ADMIN, "2026")
    assert [item["name"] for item in snapshot["participants"]] == ["Ana", "Beto"]
    assert len(snapshot["bets"]) == 2
    ana = next(item for item in snapshot["reports"] if item["user_id"] == 7)
    beto = next(item for item in snapshot["reports"] if item["user_id"] == 8)
    assert ana["manual_races"] == ["GP A"] and ana["missing_races"] == ["GP B"]
    assert beto["automatic_races"] == ["GP A"] and beto["automatic_total"] == 1


def test_participant_cannot_read_admin_bets():
    with pytest.raises(AuthorizationDenied):
        get_admin_bets(PARTICIPANT, "2026")


def test_generate_automatic_bet_reuses_legacy_service_and_target():
    with patch("services.admin_bets_v4_service._load_frames", return_value=_frames()), patch("services.bets_write.gerar_aposta_automatica", return_value=(True, "Aposta automática gerada!")) as generate:
        message = generate_admin_bet(ADMIN, "2026", 7, 20)
    assert message == "Aposta automática gerada!"
    assert generate.call_args.args[:3] == (7, 20, "GP B")
    assert generate.call_args.kwargs["temporada"] == "2026"


def test_race_reminder_sends_only_missing_participants_in_bcc():
    with patch("services.admin_bets_v4_service._load_frames", return_value=_frames()), patch("services.email_service.enviar_email", return_value=True) as send, patch("db.repo_observability.record_event"):
        recipients = send_admin_bet_reminder(ADMIN, "2026", 20)
    assert recipients == 2
    assert send.call_args.args[0] == ""
    assert send.call_args.kwargs["cco"] == ["ana@example.com", "beto@example.com"]


def test_user_reminder_has_one_direct_recipient_and_rejects_existing_bet():
    with patch("services.admin_bets_v4_service._load_frames", return_value=_frames()), patch("services.email_service.enviar_email", return_value=True) as send, patch("db.repo_observability.record_event"):
        recipients = send_admin_bet_reminder(ADMIN, "2026", 20, 7)
    assert recipients == 1
    assert send.call_args.args[0] == "ana@example.com"
    assert "cco" not in send.call_args.kwargs

    with patch("services.admin_bets_v4_service._load_frames", return_value=_frames()), pytest.raises(ValueError, match="já possui aposta"):
        send_admin_bet_reminder(ADMIN, "2026", 10, 7)
