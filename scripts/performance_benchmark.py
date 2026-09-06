#!/usr/bin/env python3
"""Benchmark PostgreSQL reproduzível para uma cópia segura do BF1.

Cria um schema isolado, gera 5–10 temporadas determinísticas, mede as jornadas
críticas e captura EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) das leituras.
Nunca aceita a mesma identidade de banco configurada em DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse


READS = {
    "login": "SELECT id, nome FROM usuarios WHERE email=%s AND status='ativo' LIMIT 1",
    "abertura_painel": "SELECT id, nome, data FROM provas WHERE temporada=%s ORDER BY data LIMIT 24",
    "classificacao": "SELECT usuario_id, SUM(pontos) total FROM posicoes_participantes WHERE temporada=%s GROUP BY usuario_id ORDER BY total DESC LIMIT 100",
    "historico": "SELECT temporada, SUM(pontos) total FROM posicoes_participantes WHERE usuario_id=%s GROUP BY temporada ORDER BY temporada",
}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]


def database_identity(url: str) -> tuple[str, int, str, str]:
    parsed = urlparse(url)
    return ((parsed.hostname or "").lower(), parsed.port or 5432, unquote(parsed.username or ""), unquote(parsed.path.lstrip("/")))


def assert_safe_copy(benchmark_url: str, production_url: str, confirmed: bool) -> None:
    if not confirmed:
        raise SystemExit("Confirme a cópia segura com --confirm-safe-copy")
    if production_url and database_identity(benchmark_url) == database_identity(production_url):
        raise SystemExit("Banco de benchmark coincide com DATABASE_URL; execução recusada")


def measured_samples(conn, query: str, params: tuple, iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        conn.execute(query, params).fetchall()
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def summarize(samples: list[float]) -> dict[str, float]:
    return {"p50_ms": round(statistics.median(samples), 2), "p95_ms": round(percentile(samples, .95), 2), "min_ms": round(min(samples), 2), "max_ms": round(max(samples), 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, choices=range(5, 11), default=10)
    parser.add_argument("--users", type=int, choices=range(10, 501), default=100)
    parser.add_argument("--races", type=int, choices=range(10, 31), default=24)
    parser.add_argument("--iterations", type=int, choices=range(5, 101), default=30)
    parser.add_argument("--confirm-safe-copy", action="store_true")
    args = parser.parse_args()
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise SystemExit("psycopg não instalado; execute pip install -r requirements.txt") from exc

    url = os.environ.get("BENCHMARK_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("BENCHMARK_DATABASE_URL é obrigatória")
    assert_safe_copy(url, os.environ.get("DATABASE_URL", "").strip(), args.confirm_safe_copy)

    schema = f"bf1_bench_{uuid.uuid4().hex[:10]}"
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "dataset": {"seasons": args.seasons, "users": args.users, "races_per_season": args.races, "iterations": args.iterations, "expected_bets": args.seasons * args.users * args.races},
        "schema": schema,
        "workloads": {},
    }
    with psycopg.connect(url, autocommit=True, application_name="bf1_performance_benchmark") as conn:
        try:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("CREATE TABLE usuarios(id bigint PRIMARY KEY, nome text, email text, status text)")
            conn.execute("CREATE UNIQUE INDEX ON usuarios(email)")
            conn.execute("CREATE TABLE provas(id bigint PRIMARY KEY, temporada text, data date, nome text)")
            conn.execute("CREATE TABLE posicoes_participantes(prova_id bigint, usuario_id bigint, temporada text, posicao int, pontos numeric)")
            conn.execute("CREATE TABLE apostas(id bigint GENERATED ALWAYS AS IDENTITY, prova_id bigint, usuario_id bigint, temporada text, data_envio timestamptz DEFAULT now(), UNIQUE(prova_id,usuario_id,temporada))")
            conn.execute("CREATE TABLE resultados(prova_id bigint PRIMARY KEY, temporada text, posicoes jsonb, atualizado_em timestamptz DEFAULT now())")
            conn.execute("CREATE INDEX ON provas(temporada,data)")
            conn.execute("CREATE INDEX ON posicoes_participantes(temporada,usuario_id,prova_id)")
            conn.execute("CREATE INDEX ON apostas(usuario_id,prova_id,temporada)")
            conn.execute("INSERT INTO usuarios SELECT u,'Usuario '||u,'user'||u||'@example.test','ativo' FROM generate_series(1,%s) u", (args.users,))
            start_year = 2026 - args.seasons + 1
            race_id = 1
            for year in range(start_year, 2027):
                for race in range(args.races):
                    conn.execute("INSERT INTO provas VALUES(%s,%s,make_date(%s,1,1)+%s,%s)", (race_id, str(year), year, race * 7, f"GP {race + 1}"))
                    conn.execute("INSERT INTO posicoes_participantes SELECT %s,u,%s,u,(101-u)::numeric FROM generate_series(1,%s) u", (race_id, str(year), args.users))
                    conn.execute("INSERT INTO apostas(prova_id,usuario_id,temporada) SELECT %s,u,%s FROM generate_series(1,%s) u", (race_id, str(year), args.users))
                    race_id += 1
            conn.execute("ANALYZE")

            params = {"login": ("user1@example.test",), "abertura_painel": ("2026",), "classificacao": ("2026",), "historico": (1,)}
            workloads = report["workloads"]
            assert isinstance(workloads, dict)
            for name, query in READS.items():
                samples = measured_samples(conn, query, params[name], args.iterations)
                explain = conn.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, params[name]).fetchone()[0]
                workloads[name] = {**summarize(samples), "explain": explain}

            bet_samples: list[float] = []
            for user_id in range(args.users + 1, args.users + 1 + args.iterations):
                started = time.perf_counter()
                conn.execute("INSERT INTO apostas(prova_id,usuario_id,temporada) VALUES(%s,%s,%s) ON CONFLICT(prova_id,usuario_id,temporada) DO UPDATE SET data_envio=now()", (race_id - 1, user_id, "2026"))
                bet_samples.append((time.perf_counter() - started) * 1000)
            workloads["envio_aposta"] = summarize(bet_samples)

            result_samples: list[float] = []
            for index in range(args.iterations):
                started = time.perf_counter()
                conn.execute("INSERT INTO resultados(prova_id,temporada,posicoes) VALUES(%s,%s,%s::jsonb) ON CONFLICT(prova_id) DO UPDATE SET posicoes=EXCLUDED.posicoes, atualizado_em=now()", (race_id - 1, "2026", json.dumps({"1": f"Piloto {index % 20}"})))
                result_samples.append((time.perf_counter() - started) * 1000)
            workloads["lancamento_resultado"] = summarize(result_samples)

            violations = []
            for workload, result in workloads.items():
                target = 1500 if workload in {"envio_aposta", "lancamento_resultado"} else 1000
                if result["p95_ms"] >= target:
                    violations.append({"workload": workload, "p95_ms": result["p95_ms"], "target_ms": target})
            report["targets"] = {"read_p95_ms": 1000, "bet_submission_p95_ms": 1500, "result_submission_p95_ms": 1500, "violations": violations}
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        finally:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


if __name__ == "__main__":
    main()
