"""Encerramento da sessão interna.

Cookies persistentes client-side foram removidos: eles não podem oferecer a
garantia HttpOnly. A persistência segura fica a cargo do OIDC nativo do
Streamlit, em :mod:`ui.oidc_auth`.
"""

from __future__ import annotations

from app_runtime import get_session
from services.auth_service import revoke_token


def clear_auth_cookies(token: str | None = None) -> None:
    token = token if token is not None else get_session().get("token")
    revoke_token(token)
