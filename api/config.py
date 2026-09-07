"""Configuração explícita do adaptador HTTP V4."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in os.environ.get(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class ApiSettings:
    cookie_name: str = os.environ.get("AUTH_COOKIE_NAME", "bf1_session")
    csrf_cookie_name: str = os.environ.get("CSRF_COOKIE_NAME", "bf1_csrf")
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
    allowed_origins: tuple[str, ...] = _csv("ALLOWED_ORIGINS", "https://bf1homol-3i2u4.ondigitalocean.app")
    log_retention_days: int = max(1, int(os.environ.get("APPLICATION_LOG_RETENTION_DAYS", "30")))
    log_export_limit: int = min(50_000, max(1, int(os.environ.get("LOG_EXPORT_MAX_ROWS", "10000"))))


settings = ApiSettings()

