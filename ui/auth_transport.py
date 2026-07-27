"""Streamlit-specific transport for the framework-neutral authentication service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import os

from app_runtime import get_session
from services.auth_service import JWT_EXP_MINUTES, revoke_token

_manager = None
_key = "bf1_auth_cookie_manager"


def _get_cookie_manager():
    global _manager
    if _manager is not None:
        return _manager
    if os.environ.get("COOKIE_BACKEND_SUPPORTS_HTTPONLY", "").strip().lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "COOKIE_BACKEND_SUPPORTS_HTTPONLY=true deve confirmar explicitamente um backend capaz de emitir HttpOnly."
        )
    try:
        stx = importlib.import_module("extra_streamlit_components")
    except ImportError as exc:
        raise RuntimeError("Backend de cookie seguro indisponível.") from exc
    _manager = stx.CookieManager(key=_key)
    return _manager


def set_auth_cookies(token: str, expires_minutes: int = JWT_EXP_MINUTES) -> None:
    _get_cookie_manager().set(
        "session_token",
        token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        options={"path": "/", "secure": True, "httponly": True, "samesite": "Strict"},
    )


def clear_auth_cookies(token: str | None = None) -> None:
    token = token if token is not None else get_session().get("token")
    revoke_token(token)
    _get_cookie_manager().set(
        "session_token",
        "",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        options={"path": "/", "secure": True, "httponly": True, "samesite": "Strict"},
    )


def get_auth_cookie_token() -> str | None:
    try:
        cookies = _get_cookie_manager().get_all()
        token = cookies.get("session_token") if isinstance(cookies, dict) else None
        return str(token) if token else None
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Falha ao ler o cookie de sessão seguro.") from exc
