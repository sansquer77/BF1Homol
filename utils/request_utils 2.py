import streamlit as st
from typing import Optional

# ---------------------------------------------------------------------------
# Notas de ambiente
# ---------------------------------------------------------------------------
# Digital Ocean App Platform (buildpack Heroku/Python) e Heroku:
#   - O proxy da plataforma APPENDA o IP real do cliente como ULTIMO segmento
#     do header X-Forwarded-For.  Exemplo real:
#       X-Forwarded-For: <forjado-pelo-cliente>, <ip-real>, <proxy-DO>
#     O segmento confiavel e sempre o ultimo adicionado pela plataforma.
#   - st.context.ip_address retorna o IP do proxy interno (ex: 100.127.x.x),
#     nao o IP do cliente — usado apenas como fallback de ultimo recurso.
#
# Streamlit Community Cloud:
#   - X-Forwarded-For nao e repassado ao runtime Python.
#   - st.context.ip_address retorna o proxy interno Tailscale (100.127.x.x).
#   - Nao ha forma de obter o IP real nesse ambiente.
# ---------------------------------------------------------------------------


def get_client_ip() -> Optional[str]:
    """Retorna o IP real do cliente, resistente a IP spoofing via XFF forjado.

    Ordem de prioridade (da mais confiavel para a menos):
    1. Ultimo segmento de X-Forwarded-For — IP appendado pelo proxy da
       plataforma (DO App Platform / Heroku).  Resistente a spoofing porque
       um atacante pode forjar segmentos a esquerda, mas nao os appendados
       pelo proxy confiavel da plataforma.
    2. X-Real-IP — presente em alguns setups nginx upstream.
    3. st.context.ip_address — fallback: pode ser IP de proxy interno.

    Retorna None quando o runtime nao expoe metadados de rede (ex: dev local).
    """
    try:
        ctx = getattr(st, "context", None)
        if not ctx:
            return None

        headers = getattr(ctx, "headers", None)

        # --- 1. X-Forwarded-For: pega o ULTIMO segmento (confiavel no DO/Heroku)
        if headers:
            xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
            if xff:
                # strip de cada segmento para lidar com espacos extras
                segments = [s.strip() for s in str(xff).split(",") if s.strip()]
                if segments:
                    return segments[-1]

            # --- 2. X-Real-IP (fallback para setups nginx)
            x_real_ip = headers.get("x-real-ip") or headers.get("X-Real-IP")
            if x_real_ip:
                return str(x_real_ip).strip() or None

        # --- 3. st.context.ip_address — ultimo recurso (pode ser proxy interno)
        ip_direct = getattr(ctx, "ip_address", None)
        if ip_direct:
            return str(ip_direct).strip() or None

    except Exception:
        return None

    return None
