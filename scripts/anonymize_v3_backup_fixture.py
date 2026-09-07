"""Gera fixture SQL determinística sem dados pessoais a partir de dump V3."""

from __future__ import annotations

import argparse
import hashlib
import re
import uuid
from pathlib import Path


FIXTURE_PASSWORD_HASH = "$2b$04$r.mdeGukB1b4FFqUP9IquOMh/Eda1S/4EDrvx19EYUgJnRp4zQ08q"
INSERT_RE = re.compile(
    r'^\s*INSERT\s+INTO\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*'
    r"\((.*?)\)\s+VALUES\s*\((.*)\);\s*$",
    re.IGNORECASE,
)


def _split_sql_csv(content: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    nesting = 0
    index = 0
    while index < len(content):
        char = content[index]
        if char == "'":
            if in_single and index + 1 < len(content) and content[index + 1] == "'":
                current.append("''")
                index += 2
                continue
            in_single = not in_single
        elif not in_single and char in "[({":
            nesting += 1
        elif not in_single and char in "]) }".replace(" ", ""):
            nesting = max(0, nesting - 1)
        if char == "," and not in_single and nesting == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    if in_single or nesting:
        raise ValueError("Literal SQL não balanceado")
    parts.append("".join(current).strip())
    return parts


def _unquote_sql(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == "'":
        return stripped[1:-1].replace("''", "'")
    return stripped


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _stable_code(kind: str, raw_value: str, size: int = 10) -> str:
    digest = hashlib.sha256(f"bf1-v4-fixture:{kind}:{raw_value}".encode()).hexdigest()
    return digest[:size]


def _anonymous_value(table: str, column: str, raw_value: str) -> str | None:
    plain = _unquote_sql(raw_value)
    if raw_value.strip().upper() == "NULL":
        return None
    if column in {"senha_hash", "password_hash"}:
        return _sql_text(FIXTURE_PASSWORD_HASH)
    if column == "jti":
        return _sql_text(str(uuid.uuid5(uuid.NAMESPACE_URL, f"bf1-v4-fixture:{plain}")))
    if column == "ip_address":
        octet = int(_stable_code("ip", plain, 2), 16) % 254 + 1
        return _sql_text(f"192.0.2.{octet}")
    if column == "email":
        return _sql_text(f"fixture-{_stable_code('email', plain)}@example.invalid")
    if column in {"nome", "user_nome", "apostador"} and table in {
        "usuarios", "access_logs", "championship_bets", "log_apostas"
    }:
        return _sql_text(f"Participante {_stable_code('name', plain, 8)}")
    if table == "access_logs" and column == "detalhes":
        return _sql_text("fixture-redacted")
    if table == "usuarios_status_historico" and column == "motivo":
        return _sql_text("fixture-redacted")
    return None


def anonymize_sql(source: str) -> str:
    output = [
        "-- BF1 POSTGRES DATA-ONLY DUMP (V3.5.0 ANONYMIZED CHARACTERIZATION FIXTURE)",
        "-- Generated deterministically. Fixture password: FixtureV4!2026",
        "-- Never replace this file with an unredacted production backup.",
    ]
    insert_count = 0
    for line_number, line in enumerate(source.splitlines(), start=1):
        if line.startswith("-- BF1 POSTGRES DATA-ONLY DUMP") or line.startswith("-- generated_at_utc:"):
            continue
        match = INSERT_RE.match(line)
        if not match:
            output.append(line)
            continue
        table, raw_columns, raw_values = match.groups()
        columns = [item.strip().strip('"') for item in _split_sql_csv(raw_columns)]
        values = _split_sql_csv(raw_values)
        if len(columns) != len(values):
            raise ValueError(
                f"INSERT inválido na linha {line_number}: {len(columns)} colunas e {len(values)} valores"
            )
        for index, column in enumerate(columns):
            replacement = _anonymous_value(table.lower(), column.lower(), values[index])
            if replacement is not None:
                values[index] = replacement
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        output.append(f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({", ".join(values)});')
        insert_count += 1
    if insert_count == 0:
        raise ValueError("Nenhum INSERT reconhecido; formato de backup incompatível")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("origem e destino devem ser arquivos diferentes")
    source = args.source.read_text(encoding="utf-8")
    anonymized = anonymize_sql(source)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(anonymized, encoding="utf-8")
    print(f"fixture anonimizada: {args.destination} ({len(anonymized.encode())} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
