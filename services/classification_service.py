"""Leitura canônica da classificação BF1 para a API V4."""

from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from services.bets_scoring import calcular_pontuacao_lote
from services.championship_service import get_championship_bets_df, get_final_results
from services.rules_service import get_regras_aplicaveis
from utils.dataframe_contracts import APOSTAS_COLUMNS, PROVAS_COLUMNS, RESULTADOS_COLUMNS, USUARIOS_COLUMNS, with_required_columns


_PNG_COLUMN_WIDTHS = (0.06, 0.34, 0.12, 0.11, 0.11, 0.14, 0.12)


def _classification_logo_path() -> Path | None:
    root = Path(__file__).resolve().parents[1]
    for candidate in (root / "BF1 2.0.png", root / "frontend" / "public" / "bf1-icon.png"):
        if candidate.is_file():
            return candidate
    return None


def calculate_totals(total: float, champion: float, vice: float, team: float, discard: float) -> dict[str, float]:
    return {
        "total": float(total),
        "champion_bonus": float(champion),
        "vice_bonus": float(vice),
        "team_bonus": float(team),
        "discard": float(discard),
        "valid_total": float(total) + float(champion) + float(vice) + float(team) - float(discard),
    }


def calculate_movement(previous_position: int | None, current_position: int) -> int | None:
    return None if previous_position is None else int(previous_position) - int(current_position)


def _format_points_br(value: float) -> str:
    return f"{float(value):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")


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
    completed_race_ids = [int(race_id) for race_id in races["id"].tolist() if int(race_id) in completed_ids]
    previous_positions: dict[int, int] = {}
    if len(completed_race_ids) > 1:
        previous_ids = set(completed_race_ids[:-1])
        previous_totals: list[tuple[int, float, int]] = []
        for order, row in enumerate(participants.to_dict("records")):
            uid = int(row["id"])
            previous_bets = completed[(completed["usuario_id"] == uid) & (completed["prova_id"].isin(previous_ids))]
            previous_total = float(pd.to_numeric(previous_bets["__points"], errors="coerce").fillna(0).sum()) if not previous_bets.empty else 0.0
            if discard_active and not previous_bets.empty:
                previous_total -= float(pd.to_numeric(previous_bets["__points"], errors="coerce").min())
            previous_totals.append((uid, previous_total, order))
        previous_totals.sort(key=lambda item: (-item[1], item[2]))
        previous_positions = {uid: position for position, (uid, _, _) in enumerate(previous_totals, start=1)}

    participant_records = participants.to_dict("records")
    for row in participant_records:
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
        entries.append({"user_id": uid, "participant": str(row["nome"]), "eleventh_hits": eleventh_hits.get(uid, 0), "championship_hits": championship_hits, **totals})

    entries.sort(key=lambda item: (-item["valid_total"], -item["eleventh_hits"], -item["championship_hits"], item["participant"]))
    previous = None
    for index, entry in enumerate(entries, start=1):
        entry["position"] = index
        entry["difference"] = 0.0 if previous is None else round(previous - entry["valid_total"], 2)
        prior_position = previous_positions.get(int(entry["user_id"]))
        entry["movement"] = calculate_movement(prior_position, index)
        entry.pop("user_id", None)
        previous = entry["valid_total"]
    race_names = {int(row["id"]): str(row.get("nome") or "Prova") for row in races.to_dict("records")}
    cumulative = {int(row["id"]): 0.0 for row in participant_records}
    names = {int(row["id"]): str(row.get("nome") or "Participante") for row in participant_records}
    race_history: list[dict[str, Any]] = []
    for race_id in completed_race_ids:
        points_by_user: dict[int, float] = {}
        for row in participant_records:
            uid = int(row["id"])
            own_race = completed[(completed["usuario_id"] == uid) & (completed["prova_id"] == race_id)]
            points = float(pd.to_numeric(own_race["__points"], errors="coerce").fillna(0).sum()) if not own_race.empty else 0.0
            points_by_user[uid] = points
            cumulative[uid] += points
        ranking = sorted(cumulative, key=lambda uid: (-cumulative[uid], names[uid]))
        positions = {uid: index for index, uid in enumerate(ranking, start=1)}
        race_history.append({
            "race_id": race_id,
            "race_name": race_names.get(race_id, f"Prova {race_id}"),
            "scores": [{
                "participant": names[uid],
                "points": round(points_by_user[uid], 2),
                "cumulative_points": round(cumulative[uid], 2),
                "position": positions[uid],
            } for uid in ranking],
        })
    return {"season": str(season), "discard_active": discard_active, "entries": entries, "races": race_history}


def classification_for_race(snapshot: dict[str, Any], race_id: int) -> dict[str, Any]:
    race = next((item for item in snapshot.get("races", []) if int(item.get("race_id", -1)) == int(race_id)), None)
    if race is None:
        raise ValueError("Prova sem classificação disponível.")
    entries = [{
        "position": score["position"],
        "participant": score["participant"],
        "total": score["points"],
        "champion_bonus": 0.0,
        "vice_bonus": 0.0,
        "team_bonus": 0.0,
        "discard": 0.0,
        "valid_total": score["points"],
        "movement": None,
    } for score in sorted(race["scores"], key=lambda item: item["position"])]
    return {"season": snapshot.get("season"), "title": f'Classificação BF1 · {race["race_name"]}', "entries": entries}


def render_classification_png(snapshot: dict[str, Any]) -> BytesIO:
    """Gera imagem limitada da tabela sem depender da UI Streamlit."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    entries = snapshot.get("entries") or []
    columns = ["Pos.", "Participante", "Total", "Bônus", "Descarte", "Total válido", "Mov."]
    def movement_label(value: int | None) -> str:
        if value is None:
            return "Novo"
        if value > 0:
            return f"↑ {value}"
        if value < 0:
            return f"↓ {abs(value)}"
        return "—"
    rows = [[item["position"], item["participant"], _format_points_br(item["total"]), _format_points_br(item["champion_bonus"] + item["vice_bonus"] + item["team_bonus"]), _format_points_br(item["discard"]), _format_points_br(item["valid_total"]), movement_label(item.get("movement"))] for item in entries]
    height = min(20.0, max(4.8, len(rows) * 0.42 + 2.4))
    width = 14.0
    dpi = max(96, min(130, int((6_100_000 / (width * height)) ** 0.5)))
    figure, axis = plt.subplots(figsize=(width, height), dpi=dpi)
    figure.subplots_adjust(left=0.025, right=0.975, top=0.82, bottom=0.055)
    axis.axis("off")
    title = snapshot.get("title") or f'Classificação BF1 · {snapshot.get("season", "")}'
    figure.text(0.5, 0.91, title, ha="center", va="center", fontsize=20, fontweight="bold")
    logo_path = _classification_logo_path()
    if logo_path:
        logo_axis = figure.add_axes((0.025, 0.835, 0.095, 0.13), anchor="NW", zorder=2)
        logo_axis.imshow(mpimg.imread(logo_path))
        logo_axis.axis("off")
    table = axis.table(
        cellText=rows or [["—", "Sem dados", "0", "0", "0", "0", "Novo"]],
        colLabels=columns,
        colWidths=_PNG_COLUMN_WIDTHS,
        bbox=(0, 0, 1, 1),
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#333842")
        if row == 0:
            cell.set_facecolor("#E10600")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#ECEEF2")
        if row > 0 and column == 1:
            cell.set_text_props(ha="left")
            cell.PAD = 0.035
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


__all__ = ["build_classification", "calculate_movement", "calculate_totals", "classification_for_race", "render_classification_png"]
