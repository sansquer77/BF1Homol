import streamlit as st
from typing import Optional


def get_client_ip() -> Optional[str]:
    """Retorna o IP do cliente quando disponível no contexto da requisição.

    Em ambientes com proxy (ex.: Heroku), prioriza o primeiro IP de X-Forwarded-For.
    Retorna None quando o runtime não expõe metadados de rede.
    """
    try:
        ctx = getattr(st, "context", None)
        if not ctx:
            return None

        ip_direct = getattr(ctx, "ip_address", None)
        if ip_direct:
            return str(ip_direct).strip() or None

        headers = getattr(ctx, "headers", None)
        if not headers:
            return None

        xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if xff:
            first = str(xff).split(",")[0].strip()
            return first or None

        x_real_ip = headers.get("x-real-ip") or headers.get("X-Real-IP")
        if x_real_ip:
            return str(x_real_ip).strip() or None
    except Exception:
        return None

    return None
