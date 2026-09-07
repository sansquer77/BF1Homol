"""Controles HTTP: origem, CSRF e cookies de sessão."""

from __future__ import annotations

import hmac
import secrets

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

