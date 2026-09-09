"""Controles HTTP: origem, CSRF e cookies de sessão."""

from __future__ import annotations

import hmac
import secrets
import time

import jwt

from fastapi import HTTPException, Request, Response, status

from api.config import settings


def validate_origin(request: Request) -> None:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin or origin not in settings.allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requisição não autorizada.")


def validate_csrf(request: Request) -> None:
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requisição não autorizada.")


def issue_session_cookies(response: Response, token: str) -> str:
    csrf = secrets.token_urlsafe(32)
    common = {"secure": settings.cookie_secure, "samesite": "lax", "path": "/", "max_age": 7200}
    response.set_cookie(settings.cookie_name, token, httponly=True, **common)
    response.set_cookie(settings.csrf_cookie_name, csrf, httponly=False, **common)
    return csrf


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.cookie_secure, httponly=False, samesite="lax")


def issue_restore_authorization_cookie(
    response: Response, *, user_id: int, session_jti: str, expires_at: float
) -> None:
    """Persiste entre requisições uma autorização curta e vinculada à sessão."""
    from services.auth_service import _get_jwt_secret

    now = int(time.time())
    expiry = max(now + 1, int(expires_at))
    token = jwt.encode(
        {
            "purpose": "backup_restore",
            "user_id": int(user_id),
            "session_jti": str(session_jti),
            "iat": now,
            "exp": expiry,
        },
        _get_jwt_secret(),
        algorithm="HS256",
    )
    response.set_cookie(
        settings.restore_cookie_name,
        token,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/api/v1/backup",
        max_age=max(1, expiry - now),
    )


def consume_restore_authorization(request: Request) -> tuple[int, str]:
    """Valida a autorização HTTP contra a sessão autenticada corrente."""
    from services.auth_service import _get_jwt_secret, decode_token

    grant_token = request.cookies.get(settings.restore_cookie_name, "")
    session_token = request.cookies.get(settings.cookie_name, "")
    try:
        grant = jwt.decode(
            grant_token,
            _get_jwt_secret(),
            algorithms=["HS256"],
            options={"require": ["purpose", "user_id", "session_jti", "iat", "exp"]},
        )
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Confirme novamente a senha do Master.") from exc
    session = decode_token(session_token) if session_token else None
    matches = bool(
        grant.get("purpose") == "backup_restore"
        and session
        and int(grant.get("user_id", 0)) == int(session.get("user_id", 0))
        and hmac.compare_digest(str(grant.get("session_jti", "")), str(session.get("jti", "")))
    )
    if not matches:
        raise HTTPException(status_code=403, detail="A confirmação não pertence à sessão atual.")
    return int(grant["user_id"]), str(grant["session_jti"])


def clear_restore_authorization_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.restore_cookie_name,
        path="/api/v1/backup",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
