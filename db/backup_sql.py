"""Operações SQL de backup/restore."""

from __future__ import annotations

from datetime import datetime


from db.backup_utils import (
    _generate_backup_sql_content,
)
from db.db_schema import db_connect
from utils.backup_security import (
    BackupLimitExceeded,
    get_backup_limits,
    require_restore_authorized,
    validate_upload_size,
)


def get_postgres_backup_mode() -> tuple[str, str]:
    return "data-only", "BF1 canonical logical dump"


def download_db(presenter) -> None:
    sql_content, mode = _generate_backup_sql_content()
    label = "Download PostgreSQL data-only backup (.sql)"

    presenter.download_button(
        label=label,
        data=sql_content.encode("utf-8"),
        file_name=f"bf1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql",
        mime="application/sql",
        on_click="ignore",
        width="stretch",
    )


def restore_backup_from_sql(sql_content: str, presenter) -> bool:
    # Um único motor evita divergência de validação entre Streamlit e API V4.
    from db.backup_utils import restore_backup_from_sql as restore_canonical_sql

    return restore_canonical_sql(sql_content, presenter)


def upload_db(presenter) -> None:
    require_restore_authorized()
    max_sql_bytes = get_backup_limits().sql_bytes
    uploaded = presenter.file_uploader(
        "Upload PostgreSQL SQL backup",
        type=["sql"],
        help=f"Only PostgreSQL SQL dumps up to {max_sql_bytes // (1024 * 1024)} MB are accepted.",
        key="upload_sql_backup",
    )
    if not uploaded:
        return

    try:
        validate_upload_size(uploaded, max_sql_bytes, "Backup SQL")
    except BackupLimitExceeded as exc:
        presenter.error(str(exc))
        return

    if presenter.button("Restore SQL backup", type="primary", width="stretch"):
        try:
            sql_text = uploaded.getvalue().decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            presenter.error("Backup SQL deve estar codificado em UTF-8 válido.")
            return
        if restore_backup_from_sql(sql_text, presenter):
            presenter.success("Backup restored successfully.")
        else:
            presenter.error("Backup restore failed.")


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
