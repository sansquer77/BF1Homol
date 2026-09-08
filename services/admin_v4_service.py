"""Casos administrativos V4 com autorização explícita por operação."""

from __future__ import annotations

from typing import Any

from services.access_control import AuthenticatedContext, AuthorizationDenied, authorize_context


def _require(context: AuthenticatedContext, operation: str, roles: frozenset[str], season: str | None = None) -> None:
    authorize_context(context, roles, season=season)


def create_user(context: AuthenticatedContext, *, name: str, email: str, password: str, profile: str, user_status: str) -> None:
    _require(context, "usuario.write", frozenset({"master"}))
    from services.auth_service import cadastrar_usuario
    if not cadastrar_usuario(name.strip(), email.strip().lower(), password, perfil=profile.strip().lower(), status=user_status.strip().lower()):
        raise ValueError("Não foi possível criar o usuário.")


def update_user(context: AuthenticatedContext, user_id: int, fields: dict[str, Any]) -> None:
    _require(context, "usuario.write", frozenset({"master"}))
    from db.repo_users import update_usuario
    allowed = {key: value for key, value in fields.items() if key in {"nome", "email", "perfil", "status", "must_change_password"}}
    if not allowed or not update_usuario(int(user_id), **allowed):
        raise ValueError("Nenhum campo administrativo válido foi alterado.")


def upsert_driver(context: AuthenticatedContext, driver_id: int | None, fields: dict[str, Any]) -> None:
    _require(context, "piloto.write", frozenset({"admin", "master"}))
    from db.repo_races import add_piloto, update_piloto
    clean = {key: value for key, value in fields.items() if key in {"nome", "equipe", "status", "numero"}}
    ok = update_piloto(int(driver_id), **clean) if driver_id is not None else add_piloto(clean.get("nome", ""), equipe=clean.get("equipe", ""), status=clean.get("status", "Ativo"), numero=int(clean.get("numero") or 0))
    if not ok:
        raise ValueError("Não foi possível salvar o piloto.")


def upsert_race(context: AuthenticatedContext, race_id: int | None, season: str, fields: dict[str, Any]) -> None:
    _require(context, "prova.write", frozenset({"admin", "master"}), season=season)
    from db.repo_races import add_prova, update_prova
    clean = {key: value for key, value in fields.items() if key in {"nome", "data", "horario_prova", "tipo", "status", "circuit_id"}}
    if race_id is None:
        ok = add_prova(clean.get("nome", ""), clean.get("data", ""), clean.get("horario_prova", ""), clean.get("tipo", "Normal"), clean.get("status", "Pendente"), season, clean.get("circuit_id"))
    else:
        clean["temporada"] = season
        ok = update_prova(int(race_id), **clean)
    if not ok:
        raise ValueError("Não foi possível salvar a prova.")


def save_result(context: AuthenticatedContext, race_id: int, season: str, positions: dict[str, Any], retirements: list[str]) -> None:
    _require(context, "resultado.write", frozenset({"admin", "master"}), season=season)
    from services.admin_operations import admin_save_resultado
    admin_save_resultado(race_id, season, positions, retirements)
