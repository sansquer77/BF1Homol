"""Validações de integridade para backup/import."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from db.db_schema import db_connect


def _sanitize_identifier(identifier: str) -> str:
    value = (identifier or "").strip()
    if not value.replace("_", "").isalnum() or not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(f"Invalid identifier: {identifier}")
    return value


def _quote_identifier(identifier: str) -> str:
    return f'"{_sanitize_identifier(identifier)}"'


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
        return [str(r["column_name"]) for r in (c.fetchall() or []) if r and r["column_name"]]


def _get_table_column_types(conn, table_name: str) -> dict[str, str]:
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        """,
        (table_name,),
    )
    return {
        str(r["column_name"]).lower(): str(r["data_type"]).lower()
        for r in (c.fetchall() or [])
        if r and r.get("column_name") and r.get("data_type")
    }


def _get_required_columns_for_insert(conn, table_name: str) -> list[str]:
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND is_nullable = 'NO'
          AND column_default IS NULL
          AND is_identity = 'NO'
          AND COALESCE(is_generated, 'NEVER') = 'NEVER'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [str(r["column_name"]) for r in (c.fetchall() or []) if r and r.get("column_name")]


def _get_fk_constraints(conn, table: str) -> list[dict[str, Any]]:
    c = conn.cursor()
    c.execute(
        """
        SELECT
            tc.constraint_name,
            kcu.column_name AS local_column,
            ccu.table_name AS parent_table,
            ccu.column_name AS parent_column,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = current_schema()
          AND tc.table_name = %s
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        (table,),
    )

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"local_columns": [], "parent_columns": [], "parent_table": ""}
    )
    for row in c.fetchall() or []:
        name = str(row["constraint_name"])
        grouped[name]["parent_table"] = str(row["parent_table"])
        grouped[name]["local_columns"].append(str(row["local_column"]))
        grouped[name]["parent_columns"].append(str(row["parent_column"]))

    constraints: list[dict[str, Any]] = []
    for name, data in grouped.items():
        constraints.append(
            {
                "constraint_name": name,
                "parent_table": data["parent_table"],
                "local_columns": data["local_columns"],
                "parent_columns": data["parent_columns"],
            }
        )
    return constraints


def _prevalidate_fk_values(
    conn,
    selected: str,
    use_cols: list[str],
    rows: list[tuple[Any, ...]],
) -> list[str]:
    if not rows:
        return []

    constraints = _get_fk_constraints(conn, selected)
    if not constraints:
        return []

    col_idx = {col: idx for idx, col in enumerate(use_cols)}
    errors: list[str] = []
    c = conn.cursor()

    for fk in constraints:
        local_cols = fk["local_columns"]
        parent_cols = fk["parent_columns"]
        parent_table = fk["parent_table"]
        fk_name = fk["constraint_name"]

        if any(col not in col_idx for col in local_cols):
            continue

        distinct_keys: set[tuple[Any, ...]] = set()
        for row in rows:
            values = tuple(row[col_idx[col]] for col in local_cols)
            if any(v is None for v in values):
                continue
            distinct_keys.add(values)

        for key_values in distinct_keys:
            where_sql = " AND ".join(f"{_quote_identifier(pc)} = %s" for pc in parent_cols)
            check_sql = (
                f"SELECT 1 FROM {_quote_identifier(parent_table)} "
                f"WHERE {where_sql} LIMIT 1"
            )
            c.execute(check_sql, key_values)
            if c.fetchone() is None:
                key_map = ", ".join(f"{lc}={val!r}" for lc, val in zip(local_cols, key_values))
                errors.append(f"FK {fk_name}: valor não encontrado em {parent_table} ({key_map})")
                if len(errors) >= 10:
                    return errors

    return errors

__all__ = [
    "_table_columns",
    "_get_table_column_types",
    "_get_required_columns_for_insert",
    "_prevalidate_fk_values",
]
