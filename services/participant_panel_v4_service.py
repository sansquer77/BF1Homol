"""Leituras sob demanda das abas pessoais da Telemetria V4."""
from __future__ import annotations

from typing import Any
import pandas as pd

from db.migrations_native_types import parse_posicoes_safe
from utils.ttl_cache import ttl_cache


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    return [] if not isinstance(frame, pd.DataFrame) or frame.empty else [dict(row) for row in frame.to_dict("records")]


def _csv(value: Any) -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _bet_value(row: dict[str, Any], native_key: str, legacy_key: str) -> Any:
    native = row.get(native_key)
    if native is None or (isinstance(native, str) and not native.strip()):
        return row.get(legacy_key)
    return native


def _allocation_contributions(
    pilots: list[str], chips: list[str], positions: dict[int, str], result: dict[str, Any] | None,
    rules: dict[str, Any], race_type: str, automatic_generation: int,
) -> list[dict[str, Any]]:
    reverse = {str(name): int(position) for position, name in positions.items()}
    if str(race_type).lower() == "sprint":
        points_table = rules.get("pontos_sprint_posicoes") or rules.get("pontos_posicoes") or [8, 7, 6, 5, 4, 3, 2, 1]
    else:
        points_table = rules.get("pontos_posicoes") or [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    retirements = set(_csv(_bet_value(result or {}, "abandono_arr", "abandono_pilotos")))
    multiplier = 2 if str(race_type).lower() == "sprint" and rules.get("pontos_dobrada") else 1
    automatic_factor = max(0.0, 1 - float(rules.get("penalidade_auto_percent", 20)) / 100) if automatic_generation >= 2 else 1.0
    allocation_rows = []
    for index, pilot in enumerate(pilots):
        chip_count = int(chips[index]) if index < len(chips) and str(chips[index]).isdigit() else 0
        actual_position = reverse.get(pilot)
        base = float(points_table[actual_position - 1]) * chip_count if actual_position and actual_position <= len(points_table) else 0.0
        if rules.get("penalidade_abandono") and pilot in retirements:
            base -= float(rules.get("pontos_penalidade", 0))
        allocation_rows.append({
            "driver": pilot, "chips": chip_count, "actual_position": actual_position,
            "points_contribution": round(base * multiplier * automatic_factor, 2),
        })
    return allocation_rows


@ttl_cache(ttl=60, tags=("personal_bets", "telemetry"))
def build_personal_bets(user_id: int, season: str) -> dict[str, Any]:
    from db.repo_bets import get_apostas_df
    from db.repo_races import get_provas_df, get_resultados_df
    from services.bets_scoring import calcular_pontuacao_lote
    from services.rules_service import get_regras_aplicaveis

    bets, races, results = get_apostas_df(season), get_provas_df(season), get_resultados_df(season)
    own = pd.DataFrame()
    if isinstance(bets, pd.DataFrame) and not bets.empty and "usuario_id" in bets:
        user_ids = pd.to_numeric(bets["usuario_id"], errors="coerce")
        own = bets[user_ids == int(user_id)].copy()
    scores = calcular_pontuacao_lote(own, results, races, temporada_descarte=season) if not own.empty else []
    race_map = {int(row["id"]): row for row in _records(races) if row.get("id") is not None}
    result_map = {int(row["prova_id"]): row for row in _records(results) if row.get("prova_id") is not None}
    race_order = {race_id: index for index, race_id in enumerate(race_map)}
    entries: list[dict[str, Any]] = []
    scored: list[tuple[str, float]] = []
    for index, row in enumerate(_records(own)):
        race_id = int(row.get("prova_id") or 0); race = race_map.get(race_id, {}); result = result_map.get(race_id)
        pilots = _csv(_bet_value(row, "pilotos_arr", "pilotos"))
        chips = _csv(_bet_value(row, "fichas_arr", "fichas"))
        positions = parse_posicoes_safe(_bet_value(result, "posicoes_jsonb", "posicoes")) if result else {}
        score = scores[index] if index < len(scores) else None
        valid_score = score is not None and pd.notna(score)
        race_type = str(race.get("tipo") or "Normal")
        automatic_generation = int(row.get("automatica") or 0)
        race_rules = get_regras_aplicaveis(season, race_type)
        if valid_score:
            scored.append((str(row.get("nome_prova") or race.get("nome") or "Prova"), float(score)))
        entries.append({
            "race_id": race_id, "race_name": str(row.get("nome_prova") or race.get("nome") or f"Prova {race_id}"),
            "race_type": race_type, "submitted_at": str(row.get("data_envio") or "") or None,
            "automatic_generation": automatic_generation, "eleventh_driver": str(row.get("piloto_11") or ""),
            "eleventh_actual": str(positions.get(11) or "") or None, "score": float(score) if valid_score else None,
            "allocations": _allocation_contributions(pilots, chips, positions, result, race_rules, race_type, automatic_generation),
        })
    entries.sort(key=lambda item: race_order.get(item["race_id"], len(race_order) + item["race_id"]))
    rules = get_regras_aplicaveis(season, "Normal")
    discard_active = bool(rules.get("descarte"))
    discard = min(scored, key=lambda item: item[1]) if discard_active and scored else None
    return {"season": str(season), "entries": entries, "discard_active": discard_active, "discard_race": discard[0] if discard else None, "discard_points": discard[1] if discard else None}


@ttl_cache(ttl=60, tags=("personal_history", "telemetry"))
def build_personal_history(user_id: int) -> dict[str, Any]:
    from db.db_schema import db_connect
    from services.hall_da_fama_controller import resolve_hall_source
    from services.historico_service import calcular_dados_grafico

    with db_connect() as conn:
        source, _ = resolve_hall_source(conn); cur = conn.cursor()
        if source == "posicoes_participantes":
            cur.execute("SELECT DISTINCT ON (temporada) temporada,posicao AS position,pontos FROM posicoes_participantes WHERE usuario_id=%s AND temporada IS NOT NULL AND posicao IS NOT NULL ORDER BY temporada,prova_id DESC NULLS LAST,id DESC", (int(user_id),))
        else:
            cur.execute("SELECT temporada,posicao_final AS position,pontos FROM hall_da_fama WHERE usuario_id=%s AND temporada IS NOT NULL AND posicao_final IS NOT NULL ORDER BY temporada", (int(user_id),))
        rows = [dict(row) for row in (cur.fetchall() or [])]; cur.close()
    entries = []
    for row in rows:
        try: entries.append({"season": str(row["temporada"]), "position": int(row["position"]), "points": float(row.get("pontos") or 0)})
        except (KeyError, TypeError, ValueError): continue
    graph = calcular_dados_grafico(int(user_id))
    latest_seasons = sorted(graph.fichas_por_temporada_piloto)[-2:]
    series = [{"season": season, "drivers": graph.fichas_por_temporada_piloto[season]} for season in latest_seasons]
    return {
        "entries": entries, "seasons_count": len(entries), "best_position": min((e["position"] for e in entries), default=None),
        "titles": sum(1 for e in entries if e["position"] == 1), "podiums": sum(1 for e in entries if e["position"] <= 3),
        "best_points": max((e["points"] for e in entries), default=None), "series": series,
    }
