"""Política fail-closed e limites de recursos para restauração de backups."""

from __future__ import annotations

import io
import os
import time
import zipfile
from dataclasses import dataclass
from typing import Any


class RestoreNotAuthorized(PermissionError):
    pass


class RestoreReauthenticationFailed(PermissionError):
    pass


class BackupLimitExceeded(ValueError):
    pass


@dataclass(frozen=True)
class BackupLimits:
    sql_bytes: int
    excel_bytes: int
    excel_uncompressed_bytes: int
    excel_rows: int
    excel_columns: int
    excel_cells: int
    excel_zip_members: int


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def get_backup_limits() -> BackupLimits:
    return BackupLimits(
        sql_bytes=_positive_env_int("BACKUP_SQL_MAX_BYTES", 10 * 1024 * 1024),
        excel_bytes=_positive_env_int("BACKUP_EXCEL_MAX_BYTES", 5 * 1024 * 1024),
        excel_uncompressed_bytes=_positive_env_int(
            "BACKUP_EXCEL_MAX_UNCOMPRESSED_BYTES", 50 * 1024 * 1024
        ),
        excel_rows=_positive_env_int("BACKUP_EXCEL_MAX_ROWS", 50_000),
        excel_columns=_positive_env_int("BACKUP_EXCEL_MAX_COLUMNS", 100),
        excel_cells=_positive_env_int("BACKUP_EXCEL_MAX_CELLS", 1_000_000),
        excel_zip_members=_positive_env_int("BACKUP_EXCEL_MAX_ZIP_MEMBERS", 200),
    )


_RESTORE_GRANT_KEY = "_backup_restore_grant"


def _reauth_ttl_seconds() -> int:
    configured = _positive_env_int("BACKUP_REAUTH_TTL_SECONDS", 600)
    return min(max(configured, 60), 1800)


def _current_restore_identity() -> tuple[int, str]:
    import streamlit as st
    from services.access_control import require_operation
    from services.auth_service import decode_token

    context = require_operation("backup.write")
    token = st.session_state.get("token")
    payload = decode_token(token) if token else None
    if not payload or int(payload.get("user_id", 0)) != context.user_id:
        raise RestoreNotAuthorized("A sessão autenticada não pôde ser revalidada.")
    jti = str(payload.get("jti") or "")
    if not jti:
        raise RestoreNotAuthorized("A sessão autenticada não possui identificador válido.")
    return context.user_id, jti


def grant_restore_authorization(*, user_id: int, jti: str) -> float:
    """Registra autorização curta; deve ser chamada somente após reautenticação no serviço."""
    import streamlit as st

    expires_at = time.time() + _reauth_ttl_seconds()
    st.session_state[_RESTORE_GRANT_KEY] = {
        "user_id": int(user_id),
        "jti": str(jti),
        "expires_at": expires_at,
    }
    return expires_at


def clear_restore_authorization() -> None:
    import streamlit as st

    st.session_state.pop(_RESTORE_GRANT_KEY, None)


def restore_authorization_error() -> str | None:
    import streamlit as st

    try:
        user_id, jti = _current_restore_identity()
    except PermissionError:
        clear_restore_authorization()
        return "A sessão precisa estar autenticada como master."

    grant = st.session_state.get(_RESTORE_GRANT_KEY)
    if not isinstance(grant, dict):
        return "Confirme novamente sua senha para habilitar a restauração."
    try:
        matches_session = (
            int(grant.get("user_id", 0)) == user_id
            and str(grant.get("jti") or "") == jti
        )
        unexpired = float(grant.get("expires_at", 0)) > time.time()
    except (TypeError, ValueError):
        matches_session = False
        unexpired = False
    if not matches_session or not unexpired:
        clear_restore_authorization()
        return "A confirmação de senha expirou ou pertence a outra sessão."
    return None


def restore_is_authorized() -> bool:
    return restore_authorization_error() is None


def require_restore_authorized() -> None:
    error = restore_authorization_error()
    if error:
        raise RestoreNotAuthorized(error)


def validate_upload_size(uploaded: Any, maximum_bytes: int, label: str) -> int:
    size = getattr(uploaded, "size", None)
    if size is None:
        buffer = uploaded.getbuffer()
        size = int(getattr(buffer, "nbytes", len(buffer)))
    size = int(size)
    if size <= 0:
        raise BackupLimitExceeded(f"{label} vazio não é permitido.")
    if size > maximum_bytes:
        raise BackupLimitExceeded(
            f"{label} excede o limite de {maximum_bytes // (1024 * 1024)} MB."
        )
    return size


def validate_sql_content_size(sql_content: str) -> int:
    maximum = get_backup_limits().sql_bytes
    size = len((sql_content or "").encode("utf-8"))
    if size <= 0:
        raise BackupLimitExceeded("Backup SQL vazio não é permitido.")
    if size > maximum:
        raise BackupLimitExceeded(
            f"Backup SQL excede o limite de {maximum // (1024 * 1024)} MB."
        )
    return size


def validate_excel_archive(content: bytes) -> None:
    limits = get_backup_limits()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > limits.excel_zip_members:
                raise BackupLimitExceeded("Excel contém arquivos internos em excesso.")
            uncompressed = sum(max(0, member.file_size) for member in members)
            if uncompressed > limits.excel_uncompressed_bytes:
                raise BackupLimitExceeded("Excel descompactado excede o limite permitido.")
    except zipfile.BadZipFile as exc:
        raise BackupLimitExceeded("Arquivo Excel inválido ou corrompido.") from exc


def validate_excel_dimensions(rows: int, columns: int) -> None:
    limits = get_backup_limits()
    cells = max(0, rows) * max(0, columns)
    if rows > limits.excel_rows:
        raise BackupLimitExceeded(f"Excel excede o limite de {limits.excel_rows} linhas.")
    if columns > limits.excel_columns:
        raise BackupLimitExceeded(f"Excel excede o limite de {limits.excel_columns} colunas.")
    if cells > limits.excel_cells:
        raise BackupLimitExceeded(f"Excel excede o limite de {limits.excel_cells} células.")


__all__ = [
    "BackupLimitExceeded",
    "BackupLimits",
    "RestoreNotAuthorized",
    "RestoreReauthenticationFailed",
    "clear_restore_authorization",
    "get_backup_limits",
    "grant_restore_authorization",
    "require_restore_authorized",
    "restore_authorization_error",
    "restore_is_authorized",
    "validate_excel_archive",
    "validate_excel_dimensions",
    "validate_sql_content_size",
    "validate_upload_size",
]
