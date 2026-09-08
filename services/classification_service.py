"""Leitura canônica da classificação BF1 para a API V4."""

from __future__ import annotations

import ast
from io import BytesIO
from typing import Any

import pandas as pd

from services.bets_scoring import calcular_pontuacao_lote
from services.championship_service import get_championship_bets_df, get_final_results
from services.rules_service import get_regras_aplicaveis
from utils.dataframe_contracts import APOSTAS_COLUMNS, PROVAS_COLUMNS, RESULTADOS_COLUMNS, USUARIOS_COLUMNS, with_required_columns


def calculate_totals(total: float, champion: float, vice: float, team: float, discard: float) -> dict[str, float]:
    return {
        "total": float(total),
        "champion_bonus": float(champion),
        "vice_bonus": float(vice),
        "team_bonus": float(team),
        "discard": float(discard),
        "valid_total": float(total) + float(champion) + float(vice) + float(team) - float(discard),
    }


def build_classification(season: str) -> dict[str, Any]:
    from db.repo_bets import get_apostas_df, get_participantes_temporada_df
    from db.repo_races import get_provas_df, get_resultados_df

    users = with_required_columns(get_participantes_temporada_df(season), USUARIOS_COLUMNS)
    races = with_required_columns(get_provas_df(season), PROVAS_COLUMNS)
    bets = with_required_columns(get_apostas_df(season), APOSTAS_COLUMNS)
    results = with_required_columns(get_resultados_df(season), RESULTADOS_COLUMNS)
    for frame, columns in ((users, ["id"]), (races, ["id"]), (bets, ["usuario_id", "prova_id"]), (results, ["prova_id"])):
        for column in columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame.dropna(subset=columns, inplace=True)
        for column in columns:
            frame[column] = frame[column].astype(int)

    participants = users[users["nome"].notna() & (users["nome"].astype(str) != "Master")]
    calculated = bets.copy()
    calculated["__points"] = [0.0 if value is None else float(value) for value in calcular_pontuacao_lote(calculated, results, races, temporada_descarte=season)] if not calculated.empty else []
    completed_ids = set(results["prova_id"].tolist())
    completed = calculated[calculated["prova_id"].isin(completed_ids)].copy()
    if "data_envio" in completed.columns:
        completed["__sent"] = pd.to_datetime(completed["data_envio"], errors="coerce")
        completed = completed.sort_values("__sent").drop_duplicates(["usuario_id", "prova_id"], keep="last")

    rules = get_regras_aplicaveis(str(season), "Normal")
    discard_active = bool(rules.get("descarte", False))
    final_result = get_final_results(int(season))
    championship_map: dict[int, dict[str, Any]] = {}
    if final_result:
        championship = get_championship_bets_df(int(season))
        for row in championship.to_dict("records"):
            try:
                championship_map[int(row.get("user_id"))] = row
            except (TypeError, ValueError):
                continue

    eleventh_hits: dict[int, int] = {}
    result_eleven: dict[int, str] = {}
    for row in results.to_dict("records"):
        try:
            positions = ast.literal_eval(str(row.get("posicoes") or "{}"))
            result_eleven[int(row["prova_id"])] = str(positions.get(11, "")).strip()
        except (ValueError, SyntaxError, TypeError):
            continue
    for row in completed.to_dict("records"):
        if str(row.get("piloto_11") or "").strip() == result_eleven.get(int(row["prova_id"]), ""):
            uid = int(row["usuario_id"])
            eleventh_hits[uid] = eleventh_hits.get(uid, 0) + 1

    entries = []
    for row in participants.to_dict("records"):
        uid = int(row["id"])
        own = completed[completed["usuario_id"] == uid]
        total = float(pd.to_numeric(own["__points"], errors="coerce").fillna(0).sum()) if not own.empty else 0.0
        discard = float(pd.to_numeric(own["__points"], errors="coerce").min()) if discard_active and not own.empty else 0.0
        champion_bonus = vice_bonus = team_bonus = 0.0
        championship_hits = 0
        championship_bet = championship_map.get(uid)
        if final_result and championship_bet:
            if championship_bet.get("champion") == final_result.get("champion"):
                champion_bonus = float(rules.get("pontos_campeao", 150)); championship_hits += 1
            if championship_bet.get("vice") == final_result.get("vice"):
                vice_bonus = float(rules.get("pontos_vice", 100)); championship_hits += 1
            if championship_bet.get("team") == final_result.get("team"):
                team_bonus = float(rules.get("pontos_equipe", 80)); championship_hits += 1
        totals = calculate_totals(total, champion_bonus, vice_bonus, team_bonus, discard)
        entries.append({"participant": str(row["nome"]), "eleventh_hits": eleventh_hits.get(uid, 0), "championship_hits": championship_hits, **totals})

    entries.sort(key=lambda item: (-item["valid_total"], -item["eleventh_hits"], -item["championship_hits"], item["participant"]))
    previous = None
    for index, entry in enumerate(entries, start=1):
        entry["position"] = index
        entry["difference"] = 0.0 if previous is None else round(previous - entry["valid_total"], 2)
        previous = entry["valid_total"]
    return {"season": str(season), "discard_active": discard_active, "entries": entries}


def render_classification_png(snapshot: dict[str, Any]) -> BytesIO:
    """Gera imagem limitada da tabela sem depender da UI Streamlit."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    entries = snapshot.get("entries") or []
    columns = ["Pos.", "Participante", "Total", "Bônus", "Descarte", "Total válido"]
    rows = [[item["position"], item["participant"], f'{item["total"]:.2f}', f'{item["champion_bonus"] + item["vice_bonus"] + item["team_bonus"]:.2f}', f'{item["discard"]:.2f}', f'{item["valid_total"]:.2f}'] for item in entries]
    height = min(20.0, max(4.8, len(rows) * 0.42 + 2.4))
    width = 14.0
    dpi = max(96, min(130, int((6_100_000 / (width * height)) ** 0.5)))
    figure, axis = plt.subplots(figsize=(width, height), dpi=dpi)
    axis.axis("off")
    axis.set_title(f'Classificação BF1 · {snapshot.get("season", "")}', fontsize=18, fontweight="bold", pad=18)
    table = axis.table(cellText=rows or [["—", "Sem dados", "0", "0", "0", "0"]], colLabels=columns, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#333842")
        if row == 0:
            cell.set_facecolor("#E10600")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#ECEEF2")
    buffer = BytesIO()
    try:
        figure.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
        buffer.seek(0)
        return buffer
    except Exception:
        buffer.close()
        raise
    finally:
        plt.close(figure)


__all__ = ["build_classification", "calculate_totals", "render_classification_png"]
