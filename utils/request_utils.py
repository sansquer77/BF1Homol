"""Resolucao de IP com topologia de proxy explicitamente configurada."""

from __future__ import annotations

import ipaddress
import os
from typing import Optional

def _valid_ip(value: object) -> Optional[str]:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def select_client_ip(mode: str, headers: object, direct_ip: object, trusted_hops: int = 0) -> Optional[str]:
    """Seleciona o IP sem inferir confiança a partir da presença de headers."""
    mode = str(mode).strip().lower()
    if mode not in {"direct", "xff", "x-real-ip"}:
        raise RuntimeError("TRUSTED_PROXY_MODE deve ser direct, xff ou x-real-ip.")
    header_map = headers or {}
    if mode == "xff":
        if trusted_hops < 1:
            raise RuntimeError("TRUSTED_PROXY_HOPS >= 1 e obrigatorio no modo xff.")
        raw = header_map.get("x-forwarded-for") or header_map.get("X-Forwarded-For")
        segments = [part.strip() for part in str(raw or "").split(",") if part.strip()]
        return _valid_ip(segments[-trusted_hops]) if len(segments) >= trusted_hops else None
    if mode == "x-real-ip":
        return _valid_ip(header_map.get("x-real-ip") or header_map.get("X-Real-IP"))
    return _valid_ip(direct_ip)


def get_client_ip() -> Optional[str]:
    """Retorna IP conforme ``TRUSTED_PROXY_MODE``.

    Modos:
    - ``direct`` (padrao): ignora todos os headers e usa ``st.context.ip_address``.
    - ``xff``: exige ``TRUSTED_PROXY_HOPS >= 1`` e seleciona o salto confiavel
      a partir da direita de ``X-Forwarded-For``.
    - ``x-real-ip``: confia exclusivamente em ``X-Real-IP``.
    """
    import streamlit as st

    mode = os.environ.get("TRUSTED_PROXY_MODE", "direct").strip().lower()

    ctx = getattr(st, "context", None)
    if not ctx:
        return None
    headers = getattr(ctx, "headers", None) or {}

    hops = 0
    if mode == "xff":
        try:
            hops = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
        except ValueError as exc:
            raise RuntimeError("TRUSTED_PROXY_HOPS invalido.") from exc
    return select_client_ip(mode, headers, getattr(ctx, "ip_address", None), hops)
