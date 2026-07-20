"""Regras puras de prazo, sem dependencia de banco ou UI."""

from datetime import datetime

from utils.datetime_utils import SAO_PAULO_TZ


def evaluate_championship_deadline(deadline: datetime | None, now: datetime) -> tuple[bool, str, datetime | None]:
    """Fail-closed: somente um instante estritamente anterior permite aposta."""
    if deadline is None:
        return False, "Apostas bloqueadas: primeira prova ou horario de largada ausente. Avise o administrador.", None
    now_sp = now if now.tzinfo is not None else now.replace(tzinfo=SAO_PAULO_TZ)
    deadline_sp = deadline if deadline.tzinfo is not None else deadline.replace(tzinfo=SAO_PAULO_TZ)
    if now_sp >= deadline_sp:
        return False, f"Apostas bloqueadas. Prazo encerrou em {deadline_sp.strftime('%d/%m/%Y %H:%M:%S')} (SP).", deadline_sp
    return True, f"Apostas liberadas ate antes de {deadline_sp.strftime('%d/%m/%Y %H:%M:%S')} (SP).", deadline_sp

