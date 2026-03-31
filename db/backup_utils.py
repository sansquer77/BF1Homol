import io
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import streamlit as st

from db.db_config import DATABASE_URL
from db.db_utils import db_connect


def _sanitize_identifier(identifier: str) -> str:
    value = (identifier or "").strip()
    if not value.replace("_", "").isalnum() or not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(f"Invalid identifier: {identifier}")
    return value


def _quote_identifier(identifier: str) -> str:
    return f'"{_sanitize_identifier(identifier)}"'


def _run_command(
    args: list[str],
    sql_input: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> tuple[bool, str, str]:
    try:
        env = os.environ.copy()
        if env_overrides:
            env.update({k: v for k, v in env_overrides.items() if v})
        result = subprocess.run(
            args,
            input=sql_input,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return False, "", f"Command not found: {args[0]}"

    return result.returncode == 0, result.stdout or "", result.stderr or ""


def _detect_cmd(candidates: tuple[str, ...]) -> str | None:
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None


def _build_pg_env_from_database_url(database_url: str) -> tuple[dict[str, str], str]:
    """Build PG* env vars from DATABASE_URL to avoid exposing credentials in argv."""
    parsed = urlparse(database_url)
    env: dict[str, str] = {}

    dbname = (parsed.path or "").lstrip("/") or "postgres"
    env["PGDATABASE"] = dbname

    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)

    query_params = parse_qs(parsed.query or "")
    for key, env_key in {
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "sslcrl": "PGSSLCRL",
        "target_session_attrs": "PGTARGETSESSIONATTRS",
    }.items():
        value = (query_params.get(key) or [""])[0]
        if value:
            env[env_key] = value

    return env, dbname


def _list_tables() -> list[str]:
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        return [str(r['table_name']) for r in (c.fetchall() or []) if r and r['table_name']]


def _order_tables_for_dump(tables: list[str]) -> list[str]:
    """Order tables to reduce FK dependency issues during statement-based restores."""
    preferred = [
        # Bases sem dependências fortes
        "usuarios",
        "temporadas",
        "circuitos_f1",
        "pilotos",
        "provas",
        # Dependentes de provas
        "resultados",
        # Dependentes de usuarios + provas
        "apostas",
        "log_apostas",
        "posicoes_participantes",
        # Dependentes de usuarios
        "usuarios_status_historico",
        "hall_da_fama",
        "championship_bets",
        "championship_bets_log",
        # Independentes / configuracões
        "championship_results",
        "regras",
        "temporadas_regras",
        "login_attempts",
        "access_logs",
        "financeiro_config_temporada",
        "financeiro_participantes",
        "password_reset_tokens",
    ]
    lower_map = {t.lower(): t for t in tables}

    ordered: list[str] = []
    seen: set[str] = set()
    for key in preferred:
        table_name = lower_map.get(key)
        if table_name and table_name not in seen:
            ordered.append(table_name)
            seen.add(table_name)

    for table_name in sorted(tables, key=str.lower):
        if table_name not in seen:
            ordered.append(table_name)
            seen.add(table_name)

    return ordered


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _get_serial_columns(conn, table: str) -> list[str]:
    """Retorna colunas com sequence associada (SERIAL / GENERATED ALWAYS AS IDENTITY)."""
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_default LIKE 'nextval%%'
        ORDER BY ordinal_position
        """,
        (table,),
    )
    rows = c.fetchall() or []
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND is_identity = 'YES'
        ORDER BY ordinal_position
        """,
        (table,),
    )
    identity_rows = c.fetchall() or []
    seen: set[str] = set()
    result: list[str] = []
    for r in rows + identity_rows:
        col = str(r['column_name'])
        if col not in seen:
            seen.add(col)
            result.append(col)
    return result


def _build_data_only_sql() -> str:
    lines: list[str] = [
        "-- BF1 POSTGRES DATA-ONLY DUMP",
        f"-- generated_at_utc: {datetime.utcnow().isoformat()}Z",
        "BEGIN;",
    ]

    tables = _order_tables_for_dump(_list_tables())
    if tables:
        trunc = ", ".join(_quote_identifier(t) for t in tables)
        lines.append(f"TRUNCATE TABLE {trunc} RESTART IDENTITY CASCADE;")

    sequence_reset_lines: list[str] = []

    with db_connect() as conn:
        c = conn.cursor()
        for table in tables:
            c.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            cols = [str(r['column_name']) for r in (c.fetchall() or []) if r and r['column_name']]
            if not cols:
                continue

            col_sql = ", ".join(_quote_identifier(cn) for cn in cols)
            c.execute(f"SELECT {col_sql} FROM {_quote_identifier(table)}")
            for row in c.fetchall() or []:
                values = ", ".join(_sql_literal(v) for v in row.values())
                lines.append(f"INSERT INTO {_quote_identifier(table)} ({col_sql}) VALUES ({values});")

            # Prepara resets de sequence para colunas SERIAL/IDENTITY
            serial_cols = _get_serial_columns(conn, table)
            for col in serial_cols:
                qt = _quote_identifier(table)
                qc = _quote_identifier(col)
                sequence_reset_lines.append(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{table}', '{col}'), "
                    f"COALESCE((SELECT MAX({qc}) FROM {qt}), 1)"
                    f");"
                )

    # Aplica resets de sequence após todos os INSERTs para evitar colisão de IDs pós-restore
    if sequence_reset_lines:
        lines.append("-- Reajusta sequences para evitar colisão de IDs pós-restore")
        lines.extend(sequence_reset_lines)

    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def _prepare_schema_for_restore() -> None:
    """Ensure base schema exists before applying data-only dumps."""
    from db.migrations import run_migrations

    run_migrations()


def _extract_truncate_tables(statement: str) -> list[str] | None:
    match = re.match(
        r"^\s*TRUNCATE\s+TABLE\s+(.+?)(?:\s+RESTART\s+IDENTITY|\s+CONTINUE\s+IDENTITY|\s+CASCADE|\s+RESTRICT|\s*$)",
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    names: list[str] = []
    for part in (match.group(1) or "").split(","):
        name = part.strip().strip('"')
        if not name:
            continue
        try:
            names.append(_sanitize_identifier(name))
        except ValueError:
            continue
    return names


def _extract_insert_table(statement: str) -> str | None:
    match = re.match(r'^\s*INSERT\s+INTO\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', statement, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return _sanitize_identifier(match.group(1))
    except ValueError:
        return None


def _is_fk_violation_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "violates foreign key constraint" in msg or "foreign key constraint" in msg


def _execute_with_savepoint(cursor, statement: str) -> tuple[bool, Exception | None]:
    cursor.execute("SAVEPOINT bf1_restore_stmt")
    try:
        cursor.execute(statement)
        cursor.execute("RELEASE SAVEPOINT bf1_restore_stmt")
        return True, None
    except Exception as exc:
        cursor.execute("ROLLBACK TO SAVEPOINT bf1_restore_stmt")
        cursor.execute("RELEASE SAVEPOINT bf1_restore_stmt")
        return False, exc


def get_postgres_backup_mode() -> tuple[str, str]:
    pg_env, dbname = _build_pg_env_from_database_url(DATABASE_URL)
    pg_dump = _detect_cmd(("pg_dump", "pg_dump16", "pg_dump15", "pg_dump14"))
    if not pg_dump:
        return "fallback", "pg_dump not found; using internal data-only dump"

    ok, _, err = _run_command([pg_dump, "--version"])
    if not ok:
        return "fallback", f"pg_dump unavailable: {err.strip() or 'unknown error'}"

    # Validate real compatibility with the target server.
    probe_ok, _, probe_err = _run_command(
        [
            pg_dump,
            "--dbname",
            dbname,
            "--schema-only",
            "--no-owner",
            "--no-privileges",
        ],
        env_overrides=pg_env,
    )
    if not probe_ok:
        probe_detail = (probe_err or "").strip() or "pg_dump probe failed"
        if "server version mismatch" in probe_detail.lower():
            return "fallback", "pg_dump version mismatch with PostgreSQL server"
        return "fallback", f"pg_dump unavailable: {probe_detail}"

    return "full", f"Compatible with {pg_dump}"


def _generate_backup_sql_content() -> tuple[str, str]:
    pg_env, dbname = _build_pg_env_from_database_url(DATABASE_URL)
    mode, detail = get_postgres_backup_mode()
    if mode == "full":
        pg_dump = _detect_cmd(("pg_dump", "pg_dump16", "pg_dump15", "pg_dump14"))
        if pg_dump:
            ok, out, err = _run_command(
                [
                    pg_dump,
                    "--dbname",
                    dbname,
                    "--no-owner",
                    "--no-privileges",
                    "--format=plain",
                    "--encoding=UTF8",
                ],
                env_overrides=pg_env,
            )
            if ok and out.strip():
                return out, "full"
            st.warning(f"pg_dump failed, using fallback. Detail: {err.strip()}")

    _ = detail
    return _build_data_only_sql(), "fallback"


def download_db() -> None:
    sql_content, mode = _generate_backup_sql_content()
    label = "Download PostgreSQL full backup (.sql)"
    if mode == "fallback":
        label = "Download PostgreSQL data-only backup (.sql)"

    st.download_button(
        label=label,
        data=sql_content.encode("utf-8"),
        file_name=f"bf1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql",
        mime="application/sql",
        width="stretch",
    )


def restore_backup_from_sql(sql_content: str) -> bool:
    is_data_only = "BF1 POSTGRES DATA-ONLY DUMP" in (sql_content[:4096] or "")
    if is_data_only:
        try:
            _prepare_schema_for_restore()
        except Exception as exc:
            st.error(f"Failed to prepare schema for restore: {exc}")
            return False

    pg_env, dbname = _build_pg_env_from_database_url(DATABASE_URL)
    psql = _detect_cmd(("psql", "psql16", "psql15", "psql14"))
    if psql:
        ok, _, err = _run_command(
            [psql, "-d", dbname, "-v", "ON_ERROR_STOP=1"],
            sql_input=sql_content,
            env_overrides=pg_env,
        )
        if ok:
            return True
        st.warning(f"psql failed, trying statement execution. Detail: {err.strip()}")

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    try:
        with db_connect() as conn:
            c = conn.cursor()
            existing_tables = {t.lower() for t in _list_tables()}
            pending_fk_inserts: list[tuple[str, str]] = []

            for stmt in statements:
                upper = stmt.upper()
                if upper in {"BEGIN", "COMMIT", "ROLLBACK"}:
                    continue

                # Ignora linhas de comentário SQL geradas no dump
                if stmt.strip().startswith("--"):
                    continue

                if upper.startswith("TRUNCATE TABLE"):
                    tables = _extract_truncate_tables(stmt)
                    if tables is not None:
                        valid_tables = [t for t in tables if t.lower() in existing_tables]
                        if not valid_tables:
                            continue
                        stmt = (
                            "TRUNCATE TABLE "
                            + ", ".join(_quote_identifier(t) for t in valid_tables)
                            + " RESTART IDENTITY CASCADE"
                        )

                insert_table = _extract_insert_table(stmt)
                if insert_table and insert_table.lower() not in existing_tables:
                    # Data-only dumps podem referenciar tabelas removidas; ignora para não abortar restore.
                    continue

                ok_stmt, err_stmt = _execute_with_savepoint(c, stmt)
                if ok_stmt:
                    continue

                if insert_table and err_stmt and _is_fk_violation_error(err_stmt):
                    pending_fk_inserts.append((stmt, str(err_stmt)))
                    continue

                raise err_stmt if err_stmt else RuntimeError("Unknown restore statement error")

            max_passes = max(2, len(existing_tables) + 1)
            for _ in range(max_passes):
                if not pending_fk_inserts:
                    break

                next_pending: list[tuple[str, str]] = []
                progress = 0
                for stmt, _last_error in pending_fk_inserts:
                    ok_stmt, err_stmt = _execute_with_savepoint(c, stmt)
                    if ok_stmt:
                        progress += 1
                        continue

                    if err_stmt and _is_fk_violation_error(err_stmt):
                        next_pending.append((stmt, str(err_stmt)))
                        continue

                    raise err_stmt if err_stmt else RuntimeError("Unknown restore statement error")

                pending_fk_inserts = next_pending
                if progress == 0:
                    break

            if pending_fk_inserts:
                first_error = pending_fk_inserts[0][1]
                raise RuntimeError(
                    "Restore failed: unresolved foreign key dependencies in "
                    f"{len(pending_fk_inserts)} INSERT statement(s). First error: {first_error}"
                )

            conn.commit()
        return True
    except Exception as exc:
        st.error(f"Restore failed: {exc}")
        return False


def upload_db() -> None:
    uploaded = st.file_uploader(
        "Upload PostgreSQL SQL backup",
        type=["sql"],
        help="Only PostgreSQL SQL dumps are accepted.",
        key="upload_sql_backup",
    )
    if not uploaded:
        return

    if st.button("Restore SQL backup", type="primary", width="stretch"):
        sql_text = uploaded.getvalue().decode("utf-8", errors="ignore")
        if restore_backup_from_sql(sql_text):
            st.success("Backup restored successfully.")
        else:
            st.error("Backup restore failed.")


def _table_columns(table_name: str) -> list[str]:
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return [str(r['column_name']) for r in (c.fetchall() or []) if r and r['column_name']]


def download_tabela() -> None:
    tables = _list_tables()
    if not tables:
        st.info("No tables found for export.")
        return

    selected = st.selectbox("Table to export", tables, key="export_table_select")
    if not selected:
        return

    with db_connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {_quote_identifier(selected)}", conn)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    buffer.seek(0)

    st.download_button(
        label=f"Download table {selected} (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"{selected}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


def upload_tabela() -> None:
    tables = _list_tables()
    if not tables:
        st.info("No tables found for import.")
        return

    selected = st.selectbox("Destination table", tables, key="import_table_select")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"], key="upload_table_xlsx")
    if not selected or not uploaded:
        return

    if st.button("Import table", type="primary", width="stretch"):
        df = pd.read_excel(uploaded)
        db_cols = _table_columns(selected)
        use_cols = [c for c in df.columns if c in db_cols]
        if not use_cols:
            st.error("No compatible columns were found.")
            return

        payload = df[use_cols].astype(object)
        placeholders = ", ".join(["%s"] * len(use_cols))
        col_sql = ", ".join(_quote_identifier(c) for c in use_cols)
        rows = []
        for row in payload.itertuples(index=False, name=None):
            rows.append(tuple(None if pd.isna(v) else v for v in row))

        with db_connect() as conn:
            c = conn.cursor()
            c.execute(f"TRUNCATE TABLE {_quote_identifier(selected)} RESTART IDENTITY CASCADE")
            c.executemany(
                f"INSERT INTO {_quote_identifier(selected)} ({col_sql}) VALUES ({placeholders})",
                rows,
            )
            conn.commit()

        st.success(f"Table {selected} imported successfully.")


def list_temporadas() -> list[str]:
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS temporadas (
                temporada TEXT PRIMARY KEY,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute("SELECT temporada FROM temporadas ORDER BY temporada")
        rows = c.fetchall() or []
        conn.commit()
    return [str(r['temporada']) for r in rows if r and r['temporada']]


def create_next_temporada() -> str:
    seasons = list_temporadas()
    if seasons:
        try:
            next_year = str(max(int(t) for t in seasons) + 1)
        except Exception:
            next_year = str(datetime.now().year + 1)
    else:
        next_year = str(datetime.now().year)

    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO temporadas (temporada)
            VALUES (%s)
            ON CONFLICT (temporada) DO NOTHING
            """,
            (next_year,),
        )
        conn.commit()

    return next_year


def migrar_sqlite_para_postgres() -> None:
    st.info("SQLite migration was removed. This app is PostgreSQL-only.")


def backup_banco(backup_dir: str = "backups") -> str:
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    sql_content, _ = _generate_backup_sql_content()
    backup_file = Path(backup_dir) / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    backup_file.write_text(sql_content, encoding="utf-8")
    return str(backup_file)


def restaurar_backup(backup_file: str) -> bool:
    try:
        sql = Path(backup_file).read_text(encoding="utf-8")
    except Exception:
        return False
    return restore_backup_from_sql(sql)
