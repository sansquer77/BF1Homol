"""Leitura, validação e processamento de resultados na interface V4."""
from __future__ import annotations

from typing import Any

import pandas as pd

from db.migrations_native_types import parse_posicoes_safe
from services.access_control import AuthenticatedContext, authorize_context
from services.painel_controller import get_prova_atual_sem_resultado_id
from services.results_service import validar_resultado


def _authorize(context: AuthenticatedContext, season: str) -> None:
    authorize_context(context, frozenset({"admin", "master"}), season=season)


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    return [] if not isinstance(frame, pd.DataFrame) or frame.empty else [dict(row) for row in frame.to_dict("records")]


def get_result_management(context: AuthenticatedContext, season: str) -> dict[str, Any]:
    _authorize(context, season)
    from db.repo_races import get_pilotos_df, get_provas_df, get_resultados_df

    races = get_provas_df(season)
    drivers = get_pilotos_df()
    results = get_resultados_df(season)
    active_drivers = [row for row in _records(drivers) if str(row.get("status") or "").strip().lower() == "ativo"]
    result_by_race = {int(row["prova_id"]): row for row in _records(results) if row.get("prova_id") is not None}
    race_items = []
    for row in _records(races):
        race_id = int(row["id"])
        result = result_by_race.get(race_id)
        positions = parse_posicoes_safe(result.get("posicoes")) if result else {}
        raw_retirements = result.get("abandono_arr") if result else None
        if isinstance(raw_retirements, (list, tuple)):
            retirements = [str(item) for item in raw_retirements if str(item).strip()]
        else:
            retirements = [item.strip() for item in str((result or {}).get("abandono_pilotos") or "").split(",") if item.strip()]
        race_items.append({
            "id": race_id, "name": str(row.get("nome") or f"Prova {race_id}"),
            "date": str(row.get("data") or ""), "time": str(row.get("horario_prova") or ""),
            "type": str(row.get("tipo") or "Normal"), "has_result": bool(result),
            "positions": {str(key): str(value) for key, value in positions.items()},
            "retirements": retirements,
        })
    return {
        "season": season,
        "selected_race_id": get_prova_atual_sem_resultado_id(races, results),
        "drivers": [{"id": int(row["id"]), "name": str(row.get("nome") or ""), "team": str(row.get("equipe") or "")} for row in active_drivers],
        "races": race_items,
    }


def save_and_process_result(
    context: AuthenticatedContext,
    race_id: int,
    season: str,
    positions: dict[str, Any],
    retirements: list[str],
) -> dict[str, Any]:
    _authorize(context, season)
    snapshot = get_result_management(context, season)
    race = next((item for item in snapshot["races"] if item["id"] == int(race_id)), None)
    if race is None:
        raise ValueError("A prova não pertence à temporada selecionada.")
    driver_names = [item["name"] for item in snapshot["drivers"]]
    normalized: dict[int, str] = {}
    for key, value in positions.items():
        try:
            position = int(key)
        except (TypeError, ValueError):
            raise ValueError("Posição de resultado inválida.") from None
        if 1 <= position <= 11 and str(value).strip():
            normalized[position] = str(value).strip()
    valid, message = validar_resultado(normalized, driver_names)
    if not valid:
        raise ValueError(message)
    clean_retirements = sorted({str(item).strip() for item in retirements if str(item).strip()})
    unknown = sorted(set(clean_retirements) - set(driver_names))
    if unknown:
        raise ValueError(f"Piloto de abandono não está ativo: {unknown[0]}.")

    from services.admin_operations import admin_save_resultado
    from services.bets_scoring import atualizar_classificacoes_todas_as_provas
    admin_save_resultado(int(race_id), season, normalized, clean_retirements)
    atualizar_classificacoes_todas_as_provas(season)

    notifications = {"sent": 0, "failed": 0, "skipped": 0, "warning": None}
    try:
        from services.result_notification_service import enviar_emails_resultado_prova
        stats = enviar_emails_resultado_prova(int(race_id), season)
        notifications.update({"sent": int(stats.enviados), "failed": int(stats.falhas), "skipped": int(stats.sem_aposta)})
        if stats.falhas:
            notifications["warning"] = f"Resultado processado, mas {stats.falhas} e-mail(s) falharam."
    except Exception:
        notifications["warning"] = "Resultado processado, mas as notificações não puderam ser enviadas."
    return {"status": "processed", "race_id": int(race_id), "notifications": notifications}


__all__ = ["get_result_management", "save_and_process_result"]
