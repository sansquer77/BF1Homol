from unittest.mock import patch

import pytest
from starlette.requests import Request
from fastapi import HTTPException

from api.dependencies import get_current_context
from services.access_control import AuthenticatedContext, AuthorizationDenied, authorize_context


def _request(path: str) -> Request:
    return Request({"type": "http", "path": path, "headers": [(b"cookie", b"bf1_session=token")], "client": ("127.0.0.1", 1234)})


def _user():
    return {"id": 7, "nome": "Ana", "email": "ana@example.com", "perfil": "participante", "status": "ativo", "must_change_password": True, "timezone": "America/Sao_Paulo"}


def test_server_rejects_protected_route_while_password_change_is_pending():
    with patch("services.auth_service.decode_token", return_value={"user_id": 7}), \
         patch("db.repo_users.get_user_by_id", return_value=_user()), \
         patch("db.repo_users.get_usuario_temporadas_ativas", return_value=[]):
        with pytest.raises(HTTPException) as error:
            get_current_context(_request("/api/v1/telemetry"))
    assert error.value.status_code == 403
    assert "Troca de senha" in str(error.value.detail)


def test_server_allows_only_identity_password_change_and_logout_paths():
    with patch("services.auth_service.decode_token", return_value={"user_id": 7}), \
         patch("db.repo_users.get_user_by_id", return_value=_user()), \
         patch("db.repo_users.get_usuario_temporadas_ativas", return_value=[]):
        for path in ("/api/v1/auth/me", "/api/v1/auth/account/password", "/api/v1/auth/logout"):
            context = get_current_context(_request(path))
            assert context.must_change_password is True


def test_service_authorization_also_blocks_pending_password_change():
    context = AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}), must_change_password=True)
    with pytest.raises(AuthorizationDenied, match="Troca de senha"):
        authorize_context(context, frozenset({"participante"}))
