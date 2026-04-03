"""Operações SQL de backup/restore."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from db.backup_repair import _repair_insert_legacy_literals
from db.backup_utils import (
    _build_data_only_sql,
    _build_pg_env_from_database_url,
    _detect_cmd,
    _execute_with_savepoint,
    _extract_insert_table,
    _extract_truncate_tables,
    _generate_backup_sql_content,
    _is_array_syntax_error,
    _is_fk_violation_error,
    _is_json_syntax_error,
    _list_tables,
    _prepare_schema_for_restore,
    _quote_identifier,
    _run_command,
    _run_fix_sequences_after_restore,
)
from db.db_config import DATABASE_URL
from db.db_schema import db_connect


def get_postgres_backup_mode() -> tuple[str, str]:
    pg_env, dbname = _build_pg_env_from_database_url(DATABASE_URL)
    pg_dump = _detect_cmd(("pg_dump", "pg_dump16", "pg_dump15", "pg_dump14"))
    if not pg_dump:
        return "fallback", "pg_dump not found; using internal data-only dump"

    ok, _, err = _run_command([pg_dump, "--version"])
    if not ok:
        return "fallback", f"pg_dump unavailable: {err.strip() or 'unknown error'}"

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
        on_click="ignore",
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
            try:
                _run_fix_sequences_after_restore()
            except Exception as exc:
                st.warning(f"Restore concluído, mas falhou ao ressincronizar sequences: {exc}")
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
                    continue

                ok_stmt, err_stmt = _execute_with_savepoint(c, stmt)
                if ok_stmt:
                    continue

                if insert_table and err_stmt and (_is_json_syntax_error(err_stmt) or _is_array_syntax_error(err_stmt)):
                    repaired_stmt = _repair_insert_legacy_literals(conn, stmt, insert_table)
                    if repaired_stmt and repaired_stmt != stmt:
                        ok_repaired, err_repaired = _execute_with_savepoint(c, repaired_stmt)
                        if ok_repaired:
                            continue
                        err_stmt = err_repaired if err_repaired else err_stmt

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

        try:
            _run_fix_sequences_after_restore()
        except Exception as exc:
            st.warning(f"Restore concluído, mas falhou ao ressincronizar sequences: {exc}")
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
    return [str(r["temporada"]) for r in rows if r and r["temporada"]]


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

__all__ = [
    "list_temporadas",
    "create_next_temporada",
    "get_postgres_backup_mode",
    "download_db",
    "restore_backup_from_sql",
    "upload_db",
]
