"""Gestão financeira V4 preservando as tabelas e regras da V3."""
from __future__ import annotations

import re
from html import escape
from typing import Any

from services.access_control import AuthenticatedContext, authorize_context

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _master(context: AuthenticatedContext, season: str) -> None:
    authorize_context(context, frozenset({"master"}), season=season)


def _participant_rows(season: str) -> list[dict[str, Any]]:
    from db.repo_bets import get_participantes_temporada_df
    frame = get_participantes_temporada_df(season)
    if frame is None or frame.empty:
        return []
    return [dict(row) for row in frame.to_dict(orient="records")]


def _money(value: float) -> float:
    return round(float(value), 2)


def get_financial(context: AuthenticatedContext, season: str) -> dict[str, Any]:
    _master(context, season)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT valor_taxa FROM financeiro_config_temporada WHERE temporada=%s", (season,))
        fee_row = cur.fetchone()
        cur.execute("SELECT usuario_id, pago FROM financeiro_participantes WHERE temporada=%s", (season,))
        payment_rows = cur.fetchall() or []
        cur.close()

    fee = _money(fee_row["valor_taxa"]) if fee_row else 0.0
    payments = {int(row["usuario_id"]): bool(row["pago"]) for row in payment_rows}
    participants: list[dict[str, Any]] = []
    for row in _participant_rows(season):
        profile = str(row.get("perfil") or row.get("profile") or "").strip().lower()
        user_id = row.get("id") or row.get("user_id")
        if profile == "master" or not user_id:
            continue
        participants.append({
            "user_id": int(user_id),
            "name": str(row.get("nome") or row.get("name") or "Participante"),
            "email": str(row.get("email") or ""),
            "paid": payments.get(int(user_id), False),
        })
    participants.sort(key=lambda item: item["name"].casefold())

    total = len(participants)
    paid = sum(1 for item in participants if item["paid"])
    total_due = _money(total * fee)
    collected = _money(paid * fee)
    summary = {
        "participants_total": total,
        "paid_total": paid,
        "pending_total": total - paid,
        "collected": collected,
        "outstanding": _money(total_due - collected),
        "total_due": total_due,
    }
    prizes = {
        "winner": _money(total_due * 0.40),
        "runner_up": _money(total_due * 0.30),
        "third": _money(total_due * 0.20),
        "administration": _money(total_due * 0.10),
    }
    return {"season": season, "fee": fee, "participants": participants, "summary": summary, "prizes": prizes}


def save_financial(context: AuthenticatedContext, season: str, fee: float, payments: dict[int, bool]) -> None:
    _master(context, season)
    if fee < 0 or len(payments) > 500 or any(int(user_id) <= 0 for user_id in payments):
        raise ValueError("Dados financeiros inválidos.")
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO financeiro_config_temporada (temporada,valor_taxa,atualizado_em)
               VALUES (%s,%s,CURRENT_TIMESTAMP)
               ON CONFLICT(temporada) DO UPDATE SET valor_taxa=EXCLUDED.valor_taxa,
               atualizado_em=CURRENT_TIMESTAMP""",
            (season, float(fee)),
        )
        for user_id, paid in payments.items():
            cur.execute(
                """INSERT INTO financeiro_participantes (usuario_id,temporada,pago,atualizado_em)
                   VALUES (%s,%s,%s,CURRENT_TIMESTAMP)
                   ON CONFLICT(usuario_id,temporada) DO UPDATE SET pago=EXCLUDED.pago,
                   atualizado_em=CURRENT_TIMESTAMP""",
                (int(user_id), season, bool(paid)),
            )
        conn.commit()
        cur.close()


def send_financial_reminder(context: AuthenticatedContext, season: str) -> int:
    _master(context, season)
    financial = get_financial(context, season)
    recipients = sorted({
        item["email"].strip().lower()
        for item in financial["participants"]
        if not item["paid"] and _EMAIL_RE.fullmatch(item["email"].strip())
    })
    if not recipients:
        raise ValueError("Não há participantes pendentes com e-mail válido.")

    from services.email_service import enviar_email
    subject = f"BF1 — pagamento pendente da temporada {season}"
    body = (
        "<p>Olá!</p><p>Identificamos que o pagamento da taxa do BF1 para a temporada "
        f"<strong>{escape(season)}</strong> ainda está pendente.</p>"
        "<p>Se você já realizou o pagamento, desconsidere esta mensagem e avise o Master.</p>"
    )
    if not enviar_email("", subject, body, cco=recipients):
        raise ValueError("Não foi possível enviar o lembrete financeiro.")

    from db.repo_observability import record_event
    record_event(
        level="INFO", category="financial", event="financial_reminder_sent",
        message="Lembrete financeiro enviado pelo Master.", user_id=context.user_id,
        metadata={"season": season, "recipient_count": len(recipients)},
    )
    return len(recipients)


__all__ = ["get_financial", "save_financial", "send_financial_reminder"]
