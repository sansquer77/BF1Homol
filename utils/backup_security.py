"""Política fail-closed e limites de recursos para restauração de backups."""

from __future__ import annotations

import io
import os
import re
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


class UnsafeSqlBackup(ValueError):
    pass


BF1_SQL_BACKUP_TABLES = frozenset(
    {
        "access_logs", "apostas", "application_logs", "auth_sessions",
        "championship_bets", "championship_bets_log", "championship_results",
        "circuitos_f1", "equipes", "financeiro_config_temporada",
        "financeiro_participantes", "hall_da_fama", "log_apostas",
        "login_attempts", "password_reset_tokens", "pilotos",
        "posicoes_participantes", "provas", "regras", "resultados",
        "temporadas", "temporadas_regras", "usuarios",
        "usuarios_status_historico",
    }
)


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
    from app_runtime import get_session
    from services.access_control import require_operation
    from services.auth_service import decode_token

    context = require_operation("backup.write")
    token = get_session().get("token")
    payload = decode_token(token) if token else None
    if not payload or int(payload.get("user_id", 0)) != context.user_id:
        raise RestoreNotAuthorized("A sessão autenticada não pôde ser revalidada.")
    jti = str(payload.get("jti") or "")
    if not jti:
        raise RestoreNotAuthorized("A sessão autenticada não possui identificador válido.")
    return context.user_id, jti


def grant_restore_authorization(*, user_id: int, jti: str) -> float:
    """Registra autorização curta; deve ser chamada somente após reautenticação no serviço."""
    from app_runtime import get_session

    expires_at = time.time() + _reauth_ttl_seconds()
    get_session()[_RESTORE_GRANT_KEY] = {
        "user_id": int(user_id),
        "jti": str(jti),
        "expires_at": expires_at,
    }
    return expires_at


def clear_restore_authorization() -> None:
    from app_runtime import get_session
    get_session().pop(_RESTORE_GRANT_KEY, None)


def restore_authorization_error() -> str | None:
    from app_runtime import get_session

    try:
        user_id, jti = _current_restore_identity()
    except PermissionError:
        clear_restore_authorization()
        return "A sessão precisa estar autenticada como master."

    grant = get_session().get(_RESTORE_GRANT_KEY)
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


_INSERT_RE = re.compile(
    rf'^INSERT\s+INTO\s+(?P<table>"[A-Za-z_][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*)'
    rf'\s*\((?P<columns>[^()]*)\)\s+VALUES\s*\((?P<values>.*)\)$',
    re.IGNORECASE | re.DOTALL,
)
_TRUNCATE_RE = re.compile(
    r'^TRUNCATE\s+TABLE\s+(?P<tables>.+?)\s+RESTART\s+IDENTITY\s+CASCADE$',
    re.IGNORECASE | re.DOTALL,
)
_SETVAL_RE = re.compile(
    r'''^SELECT\s+setval\(\s*pg_get_serial_sequence\(\s*'([A-Za-z_][A-Za-z0-9_]*)'\s*,\s*'([A-Za-z_][A-Za-z0-9_]*)'\s*\)\s*,\s*COALESCE\(\s*\(SELECT\s+MAX\(\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\)\s+FROM\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\)\s*,\s*1\s*\)\s*\)$''',
    re.IGNORECASE | re.DOTALL,
)
_NUMBER_RE = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
_IDENTIFIER_RE = re.compile(r'^(?:"([A-Za-z_][A-Za-z0-9_]*)"|([A-Za-z_][A-Za-z0-9_]*))$')


def _split_sql_statements(sql_content: str) -> list[str]:
    """Divide o dump sem interpretar `;` dentro de strings ou comentários."""
    statements: list[str] = []
    current: list[str] = []
    index = 0
    quote: str | None = None
    block_comment = False
    line_comment = False
    while index < len(sql_content):
        char = sql_content[index]
        next_char = sql_content[index + 1] if index + 1 < len(sql_content) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
                current.append(" ")
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            current.append(char)
            if char == quote:
                if next_char == quote:
                    current.append(next_char)
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char == "-" and next_char == "-":
            line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            index += 1
            continue
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if quote or block_comment:
        raise UnsafeSqlBackup("Backup SQL possui string ou comentário não finalizado.")
    trailing = "".join(current).strip()
    if trailing:
        raise UnsafeSqlBackup("Backup SQL deve terminar cada comando com ponto e vírgula.")
    return statements


def _identifier(value: str) -> str:
    match = _IDENTIFIER_RE.fullmatch(value.strip())
    if not match:
        raise UnsafeSqlBackup("Backup SQL contém identificador inválido.")
    return match.group(1) or match.group(2)


def _split_csv_literals(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    brackets = 0
    index = 0
    while index < len(value):
        char = value[index]
        next_char = value[index + 1] if index + 1 < len(value) else ""
        if quoted:
            current.append(char)
            if char == "'":
                if next_char == "'":
                    current.append(next_char)
                    index += 2
                    continue
                quoted = False
            index += 1
            continue
        if char == "'":
            quoted = True
            current.append(char)
        elif char == "[":
            brackets += 1
            current.append(char)
        elif char == "]":
            brackets -= 1
            if brackets < 0:
                raise UnsafeSqlBackup("Backup SQL contém array inválido.")
            current.append(char)
        elif char == "," and brackets == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    if quoted or brackets:
        raise UnsafeSqlBackup("Backup SQL possui literal não finalizado.")
    parts.append("".join(current).strip())
    return parts


def _validate_literal(value: str) -> None:
    if value.upper() in {"NULL", "TRUE", "FALSE"} or _NUMBER_RE.fullmatch(value):
        return
    if len(value) >= 2 and value[0] == value[-1] == "'":
        index = 1
        while index < len(value) - 1:
            if value[index] == "'":
                if index + 1 < len(value) - 1 and value[index + 1] == "'":
                    index += 2
                    continue
                raise UnsafeSqlBackup("Backup SQL contém aspas inválidas em literal.")
            index += 1
        return
    if value.upper().startswith("ARRAY[") and value.endswith("]"):
        if not value[6:-1].strip():
            return
        members = _split_csv_literals(value[6:-1])
        if not members or any(not member for member in members):
            raise UnsafeSqlBackup("Backup SQL contém array inválido.")
        for member in members:
            _validate_literal(member)
        return
    raise UnsafeSqlBackup("Backup SQL aceita apenas valores literais em INSERT.")


def validate_sql_backup_content(sql_content: str) -> list[str]:
    """Valida o formato lógico BF1 e devolve somente comandos seguros para importação.

    O upload nunca deve ser tratado como script PostgreSQL/psql. A gramática aceita
    é deliberadamente igual ao dump data-only produzido pelo BF1 3.x/4.x.
    """
    validate_sql_content_size(sql_content)
    first_nonempty = next((line.strip() for line in sql_content.splitlines() if line.strip()), "")
    if not first_nonempty.upper().startswith("-- BF1 POSTGRES DATA-ONLY DUMP"):
        raise UnsafeSqlBackup("Formato SQL não suportado. Use um backup de dados gerado pelo BF1.")
    statements = _split_sql_statements(sql_content)
    if len(statements) < 3 or statements[0].upper() != "BEGIN" or statements[-1].upper() != "COMMIT":
        raise UnsafeSqlBackup("Backup SQL deve possuir uma única transação BEGIN/COMMIT.")

    safe: list[str] = []
    truncate_seen = False
    declared_tables: set[str] = set()
    for statement in statements[1:-1]:
        upper = statement.upper()
        if upper in {"BEGIN", "COMMIT", "ROLLBACK"}:
            raise UnsafeSqlBackup("Backup SQL contém controle de transação inesperado.")
        truncate = _TRUNCATE_RE.fullmatch(statement)
        if truncate:
            if truncate_seen:
                raise UnsafeSqlBackup("Backup SQL contém mais de um TRUNCATE.")
            table_tokens = [part.strip() for part in truncate.group("tables").split(",")]
            if not table_tokens or any(not token for token in table_tokens):
                raise UnsafeSqlBackup("Backup SQL contém TRUNCATE inválido.")
            declared_tables = {_identifier(token).lower() for token in table_tokens}
            if not declared_tables.issubset(BF1_SQL_BACKUP_TABLES):
                raise UnsafeSqlBackup("Backup SQL contém tabela fora do contrato BF1.")
            truncate_seen = True
            safe.append(statement)
            continue
        insert = _INSERT_RE.fullmatch(statement)
        if insert:
            insert_table = _identifier(insert.group("table")).lower()
            if insert_table not in BF1_SQL_BACKUP_TABLES or insert_table not in declared_tables:
                raise UnsafeSqlBackup("Backup SQL contém INSERT fora das tabelas declaradas do BF1.")
            columns = [part.strip() for part in insert.group("columns").split(",")]
            if not columns or any(not column for column in columns):
                raise UnsafeSqlBackup("Backup SQL contém lista de colunas inválida.")
            normalized_columns = [_identifier(column) for column in columns]
            if len(set(normalized_columns)) != len(normalized_columns):
                raise UnsafeSqlBackup("Backup SQL contém coluna duplicada.")
            values = _split_csv_literals(insert.group("values"))
            if len(values) != len(columns):
                raise UnsafeSqlBackup("Backup SQL possui quantidade incompatível de valores.")
            for value in values:
                _validate_literal(value)
            safe.append(statement)
            continue
        setval = _SETVAL_RE.fullmatch(statement)
        if setval and setval.group(1) == setval.group(4) and setval.group(2) == setval.group(3):
            # A sequência é recalculada internamente após o commit; nunca executamos o SELECT enviado.
            continue
        raise UnsafeSqlBackup("Backup SQL contém comando não permitido.")
    if not truncate_seen:
        raise UnsafeSqlBackup("Backup SQL não contém o TRUNCATE canônico.")
    return safe


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
    "BF1_SQL_BACKUP_TABLES",
    "BackupLimits",
    "RestoreNotAuthorized",
    "RestoreReauthenticationFailed",
    "UnsafeSqlBackup",
    "clear_restore_authorization",
    "get_backup_limits",
    "grant_restore_authorization",
    "require_restore_authorized",
    "restore_authorization_error",
    "restore_is_authorized",
    "validate_excel_archive",
    "validate_excel_dimensions",
    "validate_sql_content_size",
    "validate_sql_backup_content",
    "validate_upload_size",
]
