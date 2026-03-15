import logging
import os
import signal
import smtplib
import fcntl
import hmac
from contextlib import contextmanager
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from db.backup_utils import backup_banco
from db.db_config import DB_PATH
from services.email_service import EMAIL_REMETENTE, SENHA_REMETENTE

logger = logging.getLogger(__name__)

_LOCK_FILE = Path(os.environ.get("BACKUP_TRIGGER_LOCK_FILE", "/tmp/bf1_backup_trigger.lock"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Valor inválido para %s=%s. Usando padrão %s.", name, raw, default)
        return default


def _parse_bearer(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    raw = auth_header.strip()
    if not raw:
        return ""
    parts = raw.split(" ", 1)
    if len(parts) != 2:
        return ""
    if parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


@contextmanager
def _exclusive_lock(lock_file: Path):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fp = open(lock_file, "a+")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fp.close()
        raise RuntimeError("LOCKED")

    try:
        yield
    finally:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        finally:
            fp.close()


def _send_backup_email(backup_file: Path, started_at: str, finished_at: str, duration_sec: float) -> None:
    to_email = (os.environ.get("BACKUP_TO_EMAIL") or "").strip()
    if not to_email:
        raise RuntimeError("BACKUP_TO_EMAIL não configurado")

    if not EMAIL_REMETENTE or not SENHA_REMETENTE:
        raise RuntimeError("Credenciais SMTP não configuradas (EMAIL_REMETENTE/SENHA_EMAIL)")

    subject = f"BF1 Backup Automático - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    body_html = (
        "<h3>Backup automático concluído</h3>"
        f"<p><b>Banco:</b> {DB_PATH}</p>"
        f"<p><b>Arquivo:</b> {backup_file.name}</p>"
        f"<p><b>Início (UTC):</b> {started_at}</p>"
        f"<p><b>Fim (UTC):</b> {finished_at}</p>"
        f"<p><b>Duração:</b> {duration_sec:.2f}s</p>"
    )

    msg = MIMEMultipart()
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    with open(backup_file, "rb") as f:
        attachment = MIMEApplication(f.read(), Name=backup_file.name)
    attachment["Content-Disposition"] = f'attachment; filename="{backup_file.name}"'
    msg.attach(attachment)

    smtp_timeout = max(5, _env_int("BACKUP_SMTP_TIMEOUT_SECONDS", 30))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=smtp_timeout) as server:
        server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
        server.sendmail(EMAIL_REMETENTE, [to_email], msg.as_string())


def _run_backup_workflow() -> dict[str, Any]:
    started_at = _now_iso()
    start_ts = datetime.now(timezone.utc).timestamp()

    if not Path(DB_PATH).exists():
        raise RuntimeError(f"Banco de dados não encontrado em {DB_PATH}")

    backup_path = Path(backup_banco())
    if not backup_path.exists():
        raise RuntimeError("Backup não foi criado")

    finished_at = _now_iso()
    duration_sec = datetime.now(timezone.utc).timestamp() - start_ts

    _send_backup_email(backup_path, started_at, finished_at, duration_sec)

    return {
        "ok": True,
        "message": "Backup executado e e-mail enviado com sucesso",
        "started_at": started_at,
        "finished_at": finished_at,
        "backup_file": str(backup_path),
        "db_path": str(DB_PATH),
    }


class _TimeoutError(Exception):
    pass


def _run_with_timeout(timeout_seconds: int) -> dict[str, Any]:
    timeout_seconds = max(5, int(timeout_seconds))

    def _handler(signum, frame):
        raise _TimeoutError(f"Tempo limite excedido ({timeout_seconds}s)")

    previous_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(timeout_seconds)
        return _run_backup_workflow()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def execute_backup_trigger(headers: dict[str, str] | None = None, query_token: str | None = None) -> tuple[int, dict[str, Any]]:
    started_at = _now_iso()
    headers = {k.lower(): v for k, v in (headers or {}).items()}

    configured_token = (os.environ.get("BACKUP_TRIGGER_TOKEN") or "").strip()
    if not configured_token:
        return 500, {
            "ok": False,
            "message": "BACKUP_TRIGGER_TOKEN não configurado no ambiente",
            "started_at": started_at,
            "finished_at": _now_iso(),
        }

    bearer_token = _parse_bearer(headers.get("authorization"))
    header_token = (headers.get("x-backup-token") or "").strip()
    provided_token = bearer_token or header_token or (query_token or "").strip()

    if not provided_token:
        return 401, {
            "ok": False,
            "message": "Token ausente",
            "started_at": started_at,
            "finished_at": _now_iso(),
        }

    if not hmac.compare_digest(provided_token, configured_token):
        return 403, {
            "ok": False,
            "message": "Token inválido",
            "started_at": started_at,
            "finished_at": _now_iso(),
        }

    timeout_seconds = _env_int("BACKUP_TRIGGER_TIMEOUT_SECONDS", 300)

    try:
        with _exclusive_lock(_LOCK_FILE):
            logger.info("[backup-trigger] Início da execução. db_path=%s", DB_PATH)
            workflow_start = datetime.now(timezone.utc).timestamp()
            result = _run_with_timeout(timeout_seconds)
            duration = datetime.now(timezone.utc).timestamp() - workflow_start
            logger.info("[backup-trigger] Fim com sucesso em %.2fs.", duration)
            return 200, result
    except RuntimeError as e:
        if str(e) == "LOCKED":
            return 409, {
                "ok": False,
                "message": "Backup já está em execução",
                "started_at": started_at,
                "finished_at": _now_iso(),
            }
        logger.exception("[backup-trigger] Erro de runtime")
        return 500, {
            "ok": False,
            "message": f"Erro ao executar backup: {str(e)}",
            "started_at": started_at,
            "finished_at": _now_iso(),
        }
    except _TimeoutError as e:
        logger.error("[backup-trigger] Timeout: %s", e)
        return 500, {
            "ok": False,
            "message": str(e),
            "started_at": started_at,
            "finished_at": _now_iso(),
        }
    except Exception as e:
        logger.exception("[backup-trigger] Falha inesperada")
        return 500, {
            "ok": False,
            "message": f"Falha inesperada ao executar backup: {str(e)}",
            "started_at": started_at,
            "finished_at": _now_iso(),
        }
