"""Gestão administrativa V4 das apostas de prova, compatível com a V3.5."""
from __future__ import annotations

import re
from html import escape
from typing import Any

import pandas as pd

from services.access_control import AuthenticatedContext, authorize_context

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _authorize(context: AuthenticatedContext, season: str) -> None:
    authorize_context(context, frozenset({"admin", "master"}), season=str(season))


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    return [] if not isinstance(frame, pd.DataFrame) or frame.empty else [dict(row) for row in frame.to_dict("records")]


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _csv(value: Any) -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _native_or_legacy(row: dict[str, Any], native: str, legacy: str) -> Any:
    value = row.get(native)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return row.get(legacy)
    return value


def _load_frames(season: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from db.repo_bets import get_apostas_df, get_participantes_temporada_df
    from db.repo_races import get_provas_df
    return get_participantes_temporada_df(str(season)), get_provas_df(str(season)), get_apostas_df(str(season))


def _normalized_data(season: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    participant_frame, race_frame, bet_frame = _load_frames(season)
    participants = []
    for row in _records(participant_frame):
        user_id = _integer(row.get("id") or row.get("user_id"))
        profile = str(row.get("perfil") or row.get("profile") or "participante").strip().lower()
        if not user_id or profile == "master":
            continue
        participants.append({
            "user_id": user_id,
            "name": str(row.get("nome") or row.get("name") or "Participante"),
            "email": str(row.get("email") or "").strip(),
        })
    participants.sort(key=lambda item: item["name"].casefold())

    races = []
    for row in _records(race_frame):
        race_id = _integer(row.get("id"))
        if race_id:
            races.append({
                "race_id": race_id,
                "name": str(row.get("nome") or f"Prova {race_id}"),
                "date": str(row.get("data") or "")[:10],
                "time": str(row.get("horario_prova") or "")[:8],
                "type": str(row.get("tipo") or "Normal"),
            })
    races.sort(key=lambda item: (item["date"], item["time"], item["race_id"]))

    valid_users = {item["user_id"] for item in participants}
    valid_races = {item["race_id"] for item in races}
    bets = []
    for row in _records(bet_frame):
        user_id, race_id = _integer(row.get("usuario_id")), _integer(row.get("prova_id"))
        if user_id not in valid_users or race_id not in valid_races:
            continue
        pilots = _csv(_native_or_legacy(row, "pilotos_arr", "pilotos"))
        chips = [_integer(value) for value in _csv(_native_or_legacy(row, "fichas_arr", "fichas"))]
        bets.append({
            "user_id": user_id,
            "race_id": race_id,
            "drivers": pilots,
            "chips": chips,
            "eleventh_driver": str(row.get("piloto_11") or ""),
            "submitted_at": str(row.get("data_envio") or "") or None,
            "automatic_generation": _integer(row.get("automatica")),
        })
    return participants, races, bets, (participant_frame, race_frame, bet_frame)


def get_admin_bets(context: AuthenticatedContext, season: str) -> dict[str, Any]:
    # spec: gestao-administrativa-de-apostas v0.1 — critérios 1, 6, 7 e 8
    _authorize(context, season)
    participants, races, bets, _ = _normalized_data(str(season))
    bet_map = {(item["user_id"], item["race_id"]): item for item in bets}
    reports = []
    for participant in participants:
        manual, automatic, missing = [], [], []
        for race in races:
            bet = bet_map.get((participant["user_id"], race["race_id"]))
            if not bet:
                missing.append(race["name"])
            elif bet["automatic_generation"] > 0:
                automatic.append(race["name"])
            else:
                manual.append(race["name"])
        reports.append({
            "user_id": participant["user_id"], "name": participant["name"],
            "bets_total": len(manual) + len(automatic), "manual_total": len(manual),
            "automatic_total": len(automatic), "missing_total": len(missing),
            "manual_races": manual, "automatic_races": automatic, "missing_races": missing,
        })
    return {"season": str(season), "participants": participants, "races": races, "bets": bets, "reports": reports}


def generate_admin_bet(context: AuthenticatedContext, season: str, user_id: int, race_id: int) -> str:
    # spec: gestao-administrativa-de-apostas v0.1 — critérios 4, 5 e 8
    _authorize(context, season)
    participants, races, _, frames = _normalized_data(str(season))
    participant = next((item for item in participants if item["user_id"] == int(user_id)), None)
    race = next((item for item in races if item["race_id"] == int(race_id)), None)
    if not participant or not race:
        raise ValueError("Participante ou prova não encontrado na temporada.")
    from services.bets_write import gerar_aposta_automatica
    generated, message = gerar_aposta_automatica(
        int(user_id), int(race_id), race["name"], frames[2], frames[1], temporada=str(season),
    )
    if not generated:
        raise ValueError(message or "Não foi possível gerar a aposta automática.")
    return message


def _reminder_body(participant_name: str, race: dict[str, Any]) -> str:
    deadline = " ".join(value for value in (race["date"], race["time"]) if value).strip()
    return (
        f"<p>Olá, {escape(participant_name)}!</p>"
        "<p>Seu carro ainda está na garagem: não encontramos sua aposta para "
        f"<strong>{escape(race['name'])}</strong>.</p>"
        f"<p>Registre suas escolhas antes do prazo <strong>{escape(deadline)}</strong>.</p>"
        "<p>Equipe de Organização BF1</p>"
    )


def send_admin_bet_reminder(
    context: AuthenticatedContext, season: str, race_id: int, user_id: int | None = None,
) -> int:
    # spec: gestao-administrativa-de-apostas v0.1 — critérios 2, 3 e 8
    _authorize(context, season)
    snapshot = get_admin_bets(context, str(season))
    race = next((item for item in snapshot["races"] if item["race_id"] == int(race_id)), None)
    if not race:
        raise ValueError("Prova não encontrada na temporada.")
    users_with_bet = {item["user_id"] for item in snapshot["bets"] if item["race_id"] == int(race_id)}
    candidates = [item for item in snapshot["participants"] if item["user_id"] not in users_with_bet]
    if user_id is not None:
        selected = next((item for item in snapshot["participants"] if item["user_id"] == int(user_id)), None)
        if not selected:
            raise ValueError("Participante não encontrado na temporada.")
        if selected["user_id"] in users_with_bet:
            raise ValueError("O participante selecionado já possui aposta nesta prova.")
        candidates = [selected]
    recipients = [item for item in candidates if _EMAIL_RE.fullmatch(item["email"])]
    if not recipients:
        raise ValueError("Não há participante pendente com email válido.")

    from services.email_service import enviar_email
    subject = f"BF1 — sua aposta para {race['name']} fecha em breve"
    if user_id is not None:
        recipient = recipients[0]
        sent = enviar_email(recipient["email"], subject, _reminder_body(recipient["name"], race))
    else:
        sent = enviar_email("", subject, _reminder_body("Piloto", race), cco=[item["email"] for item in recipients])
    if not sent:
        raise ValueError("Não foi possível enviar o lembrete de aposta.")
    from db.repo_observability import record_event
    record_event(
        level="INFO", category="bets", event="bet_reminder_sent",
        message="Lembrete de aposta enviado pela gestão administrativa.",
        user_id=context.user_id,
        metadata={
            "season": str(season), "race_id": int(race_id),
            "target_user_id": int(user_id) if user_id is not None else None,
            "recipient_count": len(recipients),
        },
    )
    return len(recipients)


__all__ = ["generate_admin_bet", "get_admin_bets", "send_admin_bet_reminder"]
