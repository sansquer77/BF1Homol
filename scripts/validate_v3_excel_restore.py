"""Restaura o conjunto Excel V3 pelo caminho de importação real e valida contagens."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from db import backup_excel
from db.db_schema import db_connect


RESTORE_ORDER = (
    "usuarios", "pilotos", "circuitos_f1", "regras", "temporadas",
    "temporadas_regras", "provas", "resultados", "apostas",
    "posicoes_participantes", "championship_bets", "championship_bets_log",
    "championship_results", "financeiro_config_temporada",
    "financeiro_participantes", "hall_da_fama", "auth_sessions",
    "login_attempts", "access_logs", "log_apostas", "usuarios_status_historico",
)


class Upload:
    def __init__(self, content: bytes):
        self._content = content

    def getvalue(self) -> bytes:
        return self._content

    def getbuffer(self):
        return memoryview(self._content)


class Presenter:
    def __init__(self, table: str, content: bytes):
        self.table = table
        self.upload = Upload(content)
        self.errors: list[str] = []
        self.successes: list[str] = []

    def selectbox(self, *_args, **_kwargs): return self.table
    def file_uploader(self, *_args, **_kwargs): return self.upload
    def checkbox(self, *_args, **_kwargs): return True
    def button(self, *_args, **_kwargs): return True
    def info(self, *_args, **_kwargs): pass
    def caption(self, *_args, **_kwargs): pass
    def error(self, message, **_kwargs): self.errors.append(str(message))
    def success(self, message, **_kwargs): self.successes.append(str(message))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_dir", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    backup_excel.require_restore_authorized = lambda: None
    for table in RESTORE_ORDER:
        presenter = Presenter(table, (args.fixture_dir / manifest["tables"][table]["file"]).read_bytes())
        backup_excel.upload_tabela(presenter)
        if presenter.errors or not presenter.successes:
            raise RuntimeError(f"restore {table} falhou: {presenter.errors}")
    with db_connect() as conn:
        cur = conn.cursor()
        for table, contract in manifest["tables"].items():
            cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"')
            actual = int(cur.fetchone()["n"])
            expected = int(contract["rows"])
            if actual != expected:
                raise RuntimeError(f"contagem divergente em {table}: {actual} != {expected}")
    print(f"restore Excel validado: {len(manifest['tables'])} tabelas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
