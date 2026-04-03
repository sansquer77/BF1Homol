"""Reparos de literais legados em restores."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def _sanitize_identifier(identifier: str) -> str:
    value = (identifier or "").strip()
    if not value.replace("_", "").isalnum() or not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(f"Invalid identifier: {identifier}")
    return value


def _extract_insert_columns(statement: str) -> list[str] | None:
    match = re.match(
        r'^\s*INSERT\s+INTO\s+"?[A-Za-z_][A-Za-z0-9_]*"?\s*\((.*?)\)\s+VALUES\s*\(',
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    raw_cols = match.group(1) or ""
    cols = _split_sql_csv(raw_cols)
    out: list[str] = []
    for col in cols:
        col_name = (col or "").strip().strip('"')
        if not col_name:
            return None
        try:
            out.append(_sanitize_identifier(col_name))
        except ValueError:
            return None
    return out


def _extract_values_payload(statement: str) -> str | None:
    match = re.match(
        r'^\s*INSERT\s+INTO\s+"?[A-Za-z_][A-Za-z0-9_]*"?\s*\(.*?\)\s+VALUES\s*\((.*)\)\s*$',
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return match.group(1)


def _split_sql_csv(content: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == "'":
            if in_single and i + 1 < len(content) and content[i + 1] == "'":
                current.append("''")
                i += 2
                continue
            in_single = not in_single
            current.append(ch)
            i += 1
            continue
        if ch == "," and not in_single:
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _get_json_columns(conn, table_name: str) -> set[str]:
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND data_type IN ('json', 'jsonb')
        """,
        (table_name,),
    )
    return {str(r["column_name"]).lower() for r in (c.fetchall() or []) if r and r["column_name"]}


def _get_array_columns(conn, table_name: str) -> set[str]:
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND data_type = 'ARRAY'
        """,
        (table_name,),
    )
    return {str(r["column_name"]).lower() for r in (c.fetchall() or []) if r and r["column_name"]}


def _normalize_legacy_json_sql_literal(value_literal: str) -> str | None:
    token = (value_literal or "").strip()
    if len(token) < 2 or not (token.startswith("'") and token.endswith("'")):
        return None

    inner = token[1:-1].replace("''", "'").strip()
    if not inner.startswith("{") and not inner.startswith("["):
        return None

    parsed = None
    try:
        parsed = json.loads(inner)
    except Exception:
        try:
            parsed = ast.literal_eval(inner)
        except Exception:
            return None

    fixed_json = json.dumps(parsed, ensure_ascii=False)
    escaped = fixed_json.replace("'", "''")
    return f"'{escaped}'"


def _python_to_sql_expression(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "ARRAY[" + ", ".join(_python_to_sql_expression(v) for v in value) + "]"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def _normalize_legacy_array_sql_literal(value_literal: str) -> str | None:
    token = (value_literal or "").strip()
    if len(token) < 2 or not (token.startswith("'") and token.endswith("'")):
        return None

    inner = token[1:-1].replace("''", "'").strip()
    if not (inner.startswith("[") or inner.startswith("(")):
        return None

    try:
        parsed = ast.literal_eval(inner)
    except Exception:
        return None

    if not isinstance(parsed, (list, tuple)):
        return None

    return _python_to_sql_expression(list(parsed))


def _repair_insert_json_literals(conn, statement: str, table_name: str) -> str | None:
    json_cols = _get_json_columns(conn, table_name)
    if not json_cols:
        return None

    cols = _extract_insert_columns(statement)
    payload = _extract_values_payload(statement)
    if not cols or payload is None:
        return None

    values = _split_sql_csv(payload)
    if len(cols) != len(values):
        return None

    changed = False
    for idx, col in enumerate(cols):
        if col.lower() not in json_cols:
            continue
        repaired = _normalize_legacy_json_sql_literal(values[idx])
        if repaired and repaired != values[idx]:
            values[idx] = repaired
            changed = True

    if not changed:
        return None

    return re.sub(
        r"(\\bVALUES\\s*\\().*(\\)\\s*$)",
        lambda m: f"{m.group(1)}{', '.join(values)}{m.group(2)}",
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _repair_insert_array_literals(conn, statement: str, table_name: str) -> str | None:
    array_cols = _get_array_columns(conn, table_name)
    if not array_cols:
        return None

    cols = _extract_insert_columns(statement)
    payload = _extract_values_payload(statement)
    if not cols or payload is None:
        return None

    values = _split_sql_csv(payload)
    if len(cols) != len(values):
        return None

    changed = False
    for idx, col in enumerate(cols):
        if col.lower() not in array_cols:
            continue
        repaired = _normalize_legacy_array_sql_literal(values[idx])
        if repaired and repaired != values[idx]:
            values[idx] = repaired
            changed = True

    if not changed:
        return None

    return re.sub(
        r"(\\bVALUES\\s*\\().*(\\)\\s*$)",
        lambda m: f"{m.group(1)}{', '.join(values)}{m.group(2)}",
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _repair_insert_legacy_literals(conn, statement: str, table_name: str) -> str | None:
    repaired_stmt = statement
    changed = False

    json_stmt = _repair_insert_json_literals(conn, repaired_stmt, table_name)
    if json_stmt and json_stmt != repaired_stmt:
        repaired_stmt = json_stmt
        changed = True

    array_stmt = _repair_insert_array_literals(conn, repaired_stmt, table_name)
    if array_stmt and array_stmt != repaired_stmt:
        repaired_stmt = array_stmt
        changed = True

    return repaired_stmt if changed else None

__all__ = [
    "_repair_insert_json_literals",
    "_repair_insert_array_literals",
    "_repair_insert_legacy_literals",
]
