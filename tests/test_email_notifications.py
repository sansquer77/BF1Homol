from unittest.mock import patch


def test_recovery_email_keeps_token_in_small_html_payload():
    from services.email_service import enviar_email_recuperacao_senha

    with patch("services.email_service.enviar_email", return_value=True) as send:
        assert enviar_email_recuperacao_senha("ana@example.com", "Ana", "token-123", 30)

    body = send.call_args.args[2]
    assert "token-123" in body
    assert "data:image" not in body
    assert len(body.encode("utf-8")) < 100_000


def test_invitation_email_contains_temporary_password_and_forced_change_notice():
    from services.email_service import enviar_email_convite_usuario

    with patch("services.email_service.enviar_email", return_value=True) as send:
        assert enviar_email_convite_usuario("ana@example.com", "Ana", "Senha&123")

    subject, body = send.call_args.args[1:3]
    assert subject == "Seu acesso ao BF1"
    assert "Senha&amp;123" in body
    assert "trocar esta senha no próximo login" in body
