"""Jornada V4 de apostas por prova sobre as regras e persistência legadas."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from services.access_control import AuthenticatedContext, AuthorizationDenied, authorize_context
from services.bets_rules import _aposta_valida_regras, pode_fazer_aposta
from services.rules_service import get_regras_aplicaveis


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    return frame.to_dict("records") if isinstance(frame, pd.DataFrame) and not frame.empty else []


def _active(value: object) -> bool:
    return str(value or "").strip().lower() == "ativo"


def _normalized_driver_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).split())


def _resolve_driver_name(value: object, available_names: list[str]) -> str | None:
    """Resolve nome completo ou token único sem escolher correspondência ambígua."""
    query = _normalized_driver_name(value)
    if not query:
        return None
    exact = [name for name in available_names if _normalized_driver_name(name) == query]
    if len(exact) == 1:
        return exact[0]
    token_matches = [
        name
        for name in available_names
        if query in _normalized_driver_name(name).split()
    ]
    return token_matches[0] if len(token_matches) == 1 else None


def build_race_bet_snapshot(season: str, context: AuthenticatedContext, race_id: int | None = None) -> dict[str, Any]:
    authorize_context(context, frozenset({"participante", "admin", "master"}), season=str(season))
    from db.repo_bets import get_aposta
    from db.repo_races import get_pilotos_df, get_provas_df, get_resultados_df

    races = _records(get_provas_df(str(season)))
    completed = {
        int(row["prova_id"])
        for row in _records(get_resultados_df(str(season)))
        if row.get("prova_id") is not None
    }
    race_options: list[dict[str, Any]] = []
    for row in races:
        try:
            current_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        horario_usuario = datetime.now(ZoneInfo(context.timezone)) if context.timezone else None
        can_bet, deadline_message, deadline = pode_fazer_aposta(row.get("data"), row.get("horario_prova"), horario_usuario, context.timezone)
        is_open = bool(can_bet and current_id not in completed)
        race_options.append({
            "id": current_id,
            "name": str(row.get("nome") or f"Prova {current_id}"),
            "type": str(row.get("tipo") or "Normal"),
            "date": str(row.get("data") or "")[:10],
            "time": str(row.get("horario_prova") or "")[:5],
            "is_open": is_open,
            "deadline": deadline.isoformat() if deadline else None,
            "deadline_message": deadline_message if current_id not in completed else "Aposta bloqueada: resultado já cadastrado.",
        })
    selected = next((race for race in race_options if race["id"] == race_id), None)
    if selected is None:
        selected = next((race for race in race_options if race["is_open"]), race_options[-1] if race_options else None)

    drivers = []
    for row in _records(get_pilotos_df()):
        if row.get("status") is not None and not _active(row.get("status")):
            continue
        name = str(row.get("nome") or "").strip()
        if name:
            drivers.append({"name": name, "team": str(row.get("equipe") or "")})
    drivers.sort(key=lambda item: item["name"].casefold())

    rules: dict[str, Any] = {}
    current_bet = None
    if selected:
        rules = get_regras_aplicaveis(str(season), selected["type"])
        stored = get_aposta(context.user_id, selected["id"], str(season))
        if stored:
            names = [value.strip() for value in str(stored.get("pilotos") or "").split(",") if value.strip()]
            chips = [int(value.strip()) for value in str(stored.get("fichas") or "").split(",") if value.strip()]
            current_bet = {
                "allocations": [{"driver": name, "chips": chips[index] if index < len(chips) else 0} for index, name in enumerate(names)],
                "eleventh_driver": str(stored.get("piloto_11") or ""),
                "submitted_at": str(stored.get("data_envio") or "") or None,
            }
    return {
        "season": str(season),
        "races": race_options,
        "selected_race": selected,
        "drivers": drivers,
        "rules": {
            "total_chips": int(rules.get("quantidade_fichas", 0) or 0),
            "max_chips_per_driver": int(rules.get("fichas_por_piloto", 0) or 0),
            "minimum_drivers": int(rules.get("qtd_minima_pilotos", rules.get("min_pilotos", 0)) or 0),
            "same_team_allowed": bool(rules.get("mesma_equipe", False)),
        },
        "current_bet": current_bet,
    }


def place_race_bet(season: str, race_id: int, allocations: list[dict[str, Any]], eleventh_driver: str, context: AuthenticatedContext) -> dict[str, Any]:
    authorize_context(context, frozenset({"participante", "admin", "master"}), season=str(season))
    snapshot = build_race_bet_snapshot(str(season), context, int(race_id))
    race = snapshot.get("selected_race")
    if not race or int(race["id"]) != int(race_id):
        raise ValueError("Prova não encontrada na temporada.")
    if not race["is_open"]:
        raise AuthorizationDenied("Prazo de apostas encerrado para esta prova.")
    drivers = {item["name"]: item for item in snapshot["drivers"]}
    available_names = list(drivers)
    names = [_resolve_driver_name(item.get("driver"), available_names) for item in allocations]
    eleventh_name = _resolve_driver_name(eleventh_driver, available_names)
    chips = [int(item.get("chips") or 0) for item in allocations]
    if any(name is None for name in names) or eleventh_name is None:
        raise ValueError("A aposta contém piloto indisponível.")
    canonical_names = [str(name) for name in names]
    applicable_rules = get_regras_aplicaveis(str(season), race["type"])
    drivers_frame = pd.DataFrame(snapshot["drivers"], columns=["name", "team"]).rename(columns={"name": "nome", "team": "equipe"})
    if not _aposta_valida_regras(canonical_names, chips, eleventh_name, drivers_frame, applicable_rules):
        raise ValueError("A distribuição não atende às regras vigentes.")
    errors: list[str] = []
    from services.bets_write import salvar_aposta
    saved = salvar_aposta(
        context.user_id,
        int(race_id),
        canonical_names,
        chips,
        eleventh_name,
        race["name"],
        automatica=0,
        temporada=str(season),
        show_errors=True,
        error_reporter=errors.append,
    )
    if not saved:
        raise ValueError(errors[-1] if errors else "A aposta não atende às regras vigentes.")
    return {"status": "registered", "race_id": int(race_id), "message": "Aposta registrada com sucesso."}


def generate_race_bet(season: str, race_id: int, context: AuthenticatedContext) -> dict[str, Any]:
    authorize_context(context, frozenset({"participante", "admin", "master"}), season=str(season))
    snapshot = build_race_bet_snapshot(str(season), context, int(race_id))
    race = snapshot.get("selected_race")
    if not race or int(race["id"]) != int(race_id):
        raise ValueError("Prova não encontrada na temporada.")
    if not race["is_open"]:
        raise AuthorizationDenied("Prazo de apostas encerrado para esta prova.")

    from services.bets_write import gerar_aposta_sem_ideias
    generated, message, _ = gerar_aposta_sem_ideias(
        usuario_id=context.user_id,
        prova_id=int(race_id),
        nome_prova=race["name"],
        temporada=str(season),
    )
    if not generated:
        raise ValueError(message or "Não foi possível gerar uma aposta válida.")
    return {"status": "registered", "race_id": int(race_id), "message": message}


__all__ = ["build_race_bet_snapshot", "generate_race_bet", "place_race_bet"]
