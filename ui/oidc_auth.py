"""Persistência de identidade pelo OIDC nativo do Streamlit.

O cookie de identidade é criado e protegido pelo próprio Streamlit. A aplicação
aceita apenas emails já cadastrados e continua emitindo seu JWT revogável para
autorização interna.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from db.repo_users import get_user_by_email
from services.auth_service import create_token

logger = logging.getLogger(__name__)


def oidc_enabled() -> bool:
    return os.environ.get("OIDC_AUTH_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _identity_value(identity: Any, field: str) -> Any:
    if isinstance(identity, dict):
        return identity.get(field)
    return getattr(identity, field, None)


def oidc_is_logged_in(st_module: Any) -> bool:
    if not oidc_enabled():
        return False
    try:
        return bool(_identity_value(st_module.user, "is_logged_in"))
    except Exception:
        return False


def rehydrate_oidc_session(st_module: Any) -> bool:
    """Cria a sessão interna a partir de uma identidade OIDC já validada."""
    if st_module.session_state.get("token"):
        return True
    if not oidc_is_logged_in(st_module):
        return False

    email = str(_identity_value(st_module.user, "email") or "").strip().lower()
    if not email:
        logger.warning("Identidade OIDC sem claim de email.")
        return False

    user = get_user_by_email(email)
    if not user:
        logger.warning("Email OIDC não cadastrado no BF1.")
        return False

    token = create_token(
        user_id=int(user["id"]),
        nome=str(user["nome"]),
        perfil=str(user.get("perfil") or "participante"),
        status=str(user.get("status") or "Ativo"),
    )
    st_module.session_state["token"] = token
    st_module.session_state["user_email"] = str(user.get("email") or email)
    st_module.session_state["pagina"] = "Painel do Participante"
    return True


def render_oidc_login(st_module: Any) -> None:
    if not oidc_enabled():
        return
    st_module.caption("Ou use o provedor corporativo configurado:")
    if st_module.button("Entrar com identidade segura", use_container_width=True):
        st_module.login()


def logout_oidc(st_module: Any) -> bool:
    """Encerra o cookie OIDC nativo; retorna se o logout foi iniciado."""
    if not oidc_is_logged_in(st_module):
        return False
    st_module.logout()
    return True
