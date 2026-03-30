import io
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _run_command(args: list[str], sql_input: str | None = None) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            args,
            input=sql_input,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
    except FileNotFoundError:
        return False, "", f"Command not found: {args[0]}"

    return result.returncode == 0, result.stdout or "", result.stderr or ""


def _detect_cmd(candidates: tuple[str, ...]) -> str | None:
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None


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
        return [str(r[0]) for r in (c.fetchall() or []) if r and r[0]]


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _build_data_only_sql() -> str:
    lines: list[str] = [
        "-- BF1 POSTGRES DATA-ONLY DUMP",
        f"-- generated_at_utc: {datetime.utcnow().isoformat()}Z",
        "BEGIN;",
    ]

    tables = _list_tables()
    if tables:
        trunc = ", ".join(_quote_identifier(t) for t in tables)
        lines.append(f"TRUNCATE TABLE {trunc} RESTART IDENTITY CASCADE;")

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
            cols = [str(r[0]) for r in (c.fetchall() or []) if r and r[0]]
            if not cols:
                continue

            col_sql = ", ".join(_quote_identifier(cn) for cn in cols)
            c.execute(f"SELECT {col_sql} FROM {_quote_identifier(table)}")
            for row in c.fetchall() or []:
                values = ", ".join(_sql_literal(v) for v in row)
                lines.append(f"INSERT INTO {_quote_identifier(table)} ({col_sql}) VALUES ({values});")

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


def get_postgres_backup_mode() -> tuple[str, str]:
    pg_dump = _detect_cmd(("pg_dump", "pg_dump16", "pg_dump15", "pg_dump14"))
    if not pg_dump:
        return "fallback", "pg_dump not found; using internal data-only dump"

    ok, _, err = _run_command([pg_dump, "--version"])
    if not ok:
        return "fallback", f"pg_dump unavailable: {err.strip() or 'unknown error'}"

    return "full", f"Compatible with {pg_dump}"


def _generate_backup_sql_content() -> tuple[str, str]:
    mode, detail = get_postgres_backup_mode()
    if mode == "full":
        pg_dump = _detect_cmd(("pg_dump", "pg_dump16", "pg_dump15", "pg_dump14"))
        if pg_dump:
            ok, out, err = _run_command(
                [
                    pg_dump,
                    "--dbname",
                    DATABASE_URL,
                    "--no-owner",
                    "--no-privileges",
                    "--format=plain",
                    "--encoding=UTF8",
                ]
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

    psql = _detect_cmd(("psql", "psql16", "psql15", "psql14"))
    if psql:
        ok, _, err = _run_command([psql, DATABASE_URL, "-v", "ON_ERROR_STOP=1"], sql_input=sql_content)
        if ok:
            return True
        st.warning(f"psql failed, trying statement execution. Detail: {err.strip()}")

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    try:
        with db_connect() as conn:
            c = conn.cursor()
            existing_tables = {t.lower() for t in _list_tables()}
            for stmt in statements:
                upper = stmt.upper()
                if upper in {"BEGIN", "COMMIT", "ROLLBACK"}:
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

                c.execute(stmt)
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
        return [str(r[0]) for r in (c.fetchall() or []) if r and r[0]]


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
    return [str(r[0]) for r in rows if r and r[0]]


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
