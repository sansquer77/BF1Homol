"""Casos administrativos V4 com autorização explícita por operação."""

from __future__ import annotations

from typing import Any

from services.access_control import AuthenticatedContext, authorize_context


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


def list_admin_users(context: AuthenticatedContext) -> list[dict[str, Any]]:
    _require(context, "usuario.read", frozenset({"master"}))
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur = conn.cursor(); cur.execute("SELECT id,nome,email,perfil,status,must_change_password FROM usuarios ORDER BY nome")
        rows = cur.fetchall(); cur.close()
    return [{"id": r["id"], "name": r["nome"], "email": r["email"], "profile": r["perfil"], "status": r["status"], "must_change_password": bool(r["must_change_password"])} for r in rows]


def list_admin_drivers(context: AuthenticatedContext) -> list[dict[str, Any]]:
    _require(context, "piloto.read", frozenset({"admin", "master"}))
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur = conn.cursor(); cur.execute("SELECT id,nome,equipe,status,numero FROM pilotos ORDER BY nome")
        rows = cur.fetchall(); cur.close()
    return [{"id": r["id"], "name": r["nome"], "team": r["equipe"] or "", "status": r["status"] or "Ativo", "number": r["numero"] or 0} for r in rows]


def list_admin_races(context: AuthenticatedContext, season: str) -> list[dict[str, Any]]:
    _require(context, "prova.read", frozenset({"admin", "master"}), season=season)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur = conn.cursor(); cur.execute("SELECT id,nome,data,horario_prova,tipo,status,circuit_id FROM provas WHERE temporada=%s ORDER BY data, id", (season,))
        rows = cur.fetchall(); cur.close()
    return [{"id": r["id"], "name": r["nome"], "date": str(r["data"]), "time": str(r["horario_prova"] or ""), "type": r["tipo"] or "Normal", "race_status": r["status"] or "Pendente", "circuit_id": r["circuit_id"]} for r in rows]


def list_admin_circuits(context: AuthenticatedContext) -> list[dict[str, Any]]:
    """Lista a base canônica usada no vínculo de provas da V4."""
    _require(context, "circuito.read", frozenset({"admin", "master"}))
    from db.circuitos_utils import get_circuitos_df

    records = get_circuitos_df().to_dict(orient="records")
    return [
        {
            "circuit_id": str(row.get("circuit_id") or ""),
            "circuit_name": str(row.get("circuit_name") or row.get("circuit_id") or ""),
            "country": str(row.get("country") or ""),
            "locality": str(row.get("locality") or ""),
        }
        for row in records
        if row.get("circuit_id")
    ]


def refresh_admin_circuits(context: AuthenticatedContext, season: str) -> dict[str, int]:
    """Replica a atualização V3, mantendo IDs Jolpica/Ergast padronizados."""
    _require(context, "circuito.write", frozenset({"admin", "master"}), season=season)
    from db.circuitos_utils import atualizar_base_circuitos, get_temporadas_existentes_provas

    seasons = set(get_temporadas_existentes_provas())
    seasons.add(season)
    seasons.add(str(int(season) - 1))
    stats = atualizar_base_circuitos(sorted(seasons))
    if stats.get("temporadas", 0) == 0:
        raise ValueError("A API de circuitos não respondeu para as temporadas consultadas.")
    return stats
