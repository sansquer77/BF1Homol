"""Contexto autenticado e politica central de autorizacao.

Operacoes sensiveis resolvem o token diretamente da sessao e revalidam o
usuario no banco. Campos enviados pela UI nunca constituem autoridade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, FrozenSet


class AuthenticationRequired(PermissionError):
    pass


class AuthorizationDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AuthenticatedContext:
    user_id: int
    nome: str
    perfil: str
    status: str
    temporadas_autorizadas: FrozenSet[str]

    @property
    def ativo(self) -> bool:
        return self.status == "ativo" and self.perfil != "inativo"


PAGE_ACCESS: dict[str, frozenset[str]] = {
    "Login": frozenset({"anon"}),
    "Painel do Participante": frozenset({"participante", "admin", "master", "inativo"}),
    "Calendário": frozenset({"participante", "admin", "master", "inativo"}),
    "Gestão de Usuários": frozenset({"master"}),
    "Gestão de Pilotos": frozenset({"admin", "master"}),
    "Gestão de Provas": frozenset({"admin", "master"}),
    "Gestão de Apostas": frozenset({"admin", "master"}),
    "Gestão de Regras": frozenset({"master"}),
    "Análise de Apostas": frozenset({"participante", "admin", "master", "inativo"}),
    "Atualização de resultados": frozenset({"admin", "master"}),
    "Apostas Campeonato": frozenset({"participante", "admin", "master"}),
    "Resultado Campeonato": frozenset({"admin", "master"}),
    "Log de Apostas": frozenset({"participante", "admin", "master", "inativo"}),
    "Log de Acessos": frozenset({"master"}),
    "Classificação": frozenset({"participante", "admin", "master", "inativo"}),
    "Hall da Fama": frozenset({"participante", "admin", "master", "inativo"}),
    "Dashboard F1": frozenset({"participante", "admin", "master", "inativo"}),
    "Backup dos Bancos de Dados": frozenset({"master"}),
    "Regulamento": frozenset({"participante", "admin", "master", "inativo"}),
    "Sobre": frozenset({"participante", "admin", "master", "inativo"}),
}

OPERATION_ACCESS: dict[str, frozenset[str]] = {
    "piloto.write": frozenset({"admin", "master"}),
    "prova.write": frozenset({"admin", "master"}),
    "resultado.write": frozenset({"admin", "master"}),
    "resultado_campeonato.write": frozenset({"admin", "master"}),
    "usuario.write": frozenset({"master"}),
    "regra.write": frozenset({"master"}),
    "hall_da_fama.write": frozenset({"master"}),
    "backup.write": frozenset({"master"}),
    "aposta_admin.write": frozenset({"admin", "master"}),
}


def authorize_context(context: AuthenticatedContext, allowed_roles: frozenset[str], *, season: str | None = None) -> None:
    if not context.ativo:
        raise AuthorizationDenied("Usuario inativo nao pode executar operacoes sensiveis.")
    if context.perfil not in allowed_roles:
        raise AuthorizationDenied("Perfil sem permissao para esta operacao.")
    if season and context.temporadas_autorizadas and str(season) not in context.temporadas_autorizadas:
        raise AuthorizationDenied("Temporada fora do escopo autorizado.")


def resolve_authenticated_context() -> AuthenticatedContext:
    """Revalida token e usuario; nao usa perfil/user_id informados pela UI."""
    import streamlit as st
    from db.repo_users import get_user_by_id, get_usuario_temporadas_ativas
    from services.auth_service import decode_token

    token = st.session_state.get("token")
    payload = decode_token(token) if token else None
    if not payload or not payload.get("user_id"):
        raise AuthenticationRequired("Sessao ausente ou invalida.")
    user = get_user_by_id(int(payload["user_id"]))
    if not user:
        raise AuthenticationRequired("Usuario autenticado nao existe.")
    perfil = str(user.get("perfil", "participante")).strip().lower()
    status = str(user.get("status", "")).strip().lower()
    if status != "ativo" or perfil == "inativo":
        perfil = "inativo"
    if perfil == "inativo":
        seasons = frozenset(str(s) for s in get_usuario_temporadas_ativas(int(user["id"])))
    elif perfil == "participante":
        seasons = frozenset({str(datetime.now().year)})
    else:
        seasons = frozenset()  # admin/master: escopo global, ainda autenticado
    return AuthenticatedContext(int(user["id"]), str(user.get("nome", "")), perfil, status, seasons)


def require_operation(operation: str, *, season: str | None = None) -> AuthenticatedContext:
    allowed = OPERATION_ACCESS.get(operation)
    if allowed is None:
        raise RuntimeError(f"Operacao sensivel sem politica cadastrada: {operation}")
    context = resolve_authenticated_context()
    authorize_context(context, allowed, season=season)
    return context


def page_is_allowed(page: str, role: str) -> bool:
    key = "Calendário" if page.startswith("Calendário (") else page
    return role in PAGE_ACCESS.get(key, frozenset())
