"""Gera snapshot determinístico do schema reconstruído após restore V3.x."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def snapshot(database_url: str, legacy_tables: set[str]) -> dict:
    result: dict = {"format_version": 1, "contract": "v3.x-reconstructed", "tables": {}}
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        for table in sorted(legacy_tables):
            cur = conn.cursor()
            cur.execute(
                """SELECT column_name,ordinal_position,data_type,udt_name,is_nullable,
                          CASE WHEN is_identity='YES' THEN 'identity' ELSE column_default END AS column_default
                   FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
                (table,),
            )
            columns = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """SELECT tc.constraint_name,tc.constraint_type,
                          array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS columns
                   FROM information_schema.table_constraints tc
                   LEFT JOIN information_schema.key_column_usage kcu
                     ON kcu.constraint_schema=tc.constraint_schema AND kcu.constraint_name=tc.constraint_name
                   WHERE tc.table_schema='public' AND tc.table_name=%s
                     AND tc.constraint_type IN ('PRIMARY KEY','UNIQUE')
                   GROUP BY tc.constraint_name,tc.constraint_type ORDER BY tc.constraint_type,tc.constraint_name""",
                (table,),
            )
            constraints = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """SELECT tc.constraint_name,kcu.column_name AS local_column,
                          ccu.table_name AS parent_table,ccu.column_name AS parent_column,
                          rc.update_rule,rc.delete_rule
                   FROM information_schema.table_constraints tc
                   JOIN information_schema.key_column_usage kcu
                     ON kcu.constraint_schema=tc.constraint_schema AND kcu.constraint_name=tc.constraint_name
                   JOIN information_schema.referential_constraints rc
                     ON rc.constraint_schema=tc.constraint_schema AND rc.constraint_name=tc.constraint_name
                   JOIN information_schema.constraint_column_usage ccu
                     ON ccu.constraint_schema=rc.unique_constraint_schema AND ccu.constraint_name=rc.unique_constraint_name
                   WHERE tc.table_schema='public' AND tc.table_name=%s AND tc.constraint_type='FOREIGN KEY'
                   ORDER BY tc.constraint_name,kcu.ordinal_position""",
                (table,),
            )
            foreign_keys = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """SELECT indexname,indexdef FROM pg_indexes
                   WHERE schemaname='public' AND tablename=%s ORDER BY indexname""",
                (table,),
            )
            indexes = [dict(row) for row in cur.fetchall()]
            result["tables"][table] = {
                "columns": columns,
                "constraints": constraints,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database_url")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    data = snapshot(args.database_url, set(manifest["tables"]))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
