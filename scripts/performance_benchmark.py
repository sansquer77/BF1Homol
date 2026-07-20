#!/usr/bin/env python3
"""Benchmark reproduzivel para 5--10 temporadas em uma copia segura.

Uso:
  BENCHMARK_DATABASE_URL=postgresql://... python scripts/performance_benchmark.py --seasons 10

O script cria e remove somente um schema ``bf1_bench_*``. Por seguranca ele
recusa a mesma URL de ``DATABASE_URL`` e exige ``--allow-same-database`` quando
a copia usa o mesmo servidor/database da aplicacao.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid

READS = {
    "login": "SELECT id, nome FROM usuarios WHERE email=%s AND status='ativo' LIMIT 1",
    "painel": "SELECT * FROM provas WHERE temporada=%s ORDER BY data LIMIT 24",
    "classificacao": "SELECT usuario_id, SUM(pontos) total FROM posicoes_participantes WHERE temporada=%s GROUP BY usuario_id ORDER BY total DESC LIMIT 100",
    "historico": "SELECT temporada, SUM(pontos) total FROM posicoes_participantes WHERE usuario_id=%s GROUP BY temporada ORDER BY temporada",
}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, choices=range(5, 11), default=10)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--races", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--allow-same-database", action="store_true")
    args = parser.parse_args()
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise SystemExit("psycopg nao instalado; execute pip install -r requirements.txt") from exc
    url = os.environ.get("BENCHMARK_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("BENCHMARK_DATABASE_URL e obrigatoria")
    if url == os.environ.get("DATABASE_URL", "").strip() and not args.allow_same_database:
        raise SystemExit("Banco de benchmark coincide com DATABASE_URL; use uma copia segura")

    schema = f"bf1_bench_{uuid.uuid4().hex[:10]}"
    report: dict[str, object] = {"dataset": vars(args), "schema": schema, "workloads": {}}
    with psycopg.connect(url, autocommit=True) as conn:
        try:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("CREATE TABLE usuarios(id bigint PRIMARY KEY, nome text, email text, status text)")
            conn.execute("CREATE UNIQUE INDEX ON usuarios(email)")
            conn.execute("INSERT INTO usuarios SELECT u, 'Usuario '||u, 'user'||u||'@example.test', 'ativo' FROM generate_series(1,%s) u", (args.users,))
            conn.execute("CREATE TABLE provas(id bigint PRIMARY KEY, temporada text, data date, nome text)")
            conn.execute("CREATE TABLE posicoes_participantes(prova_id bigint, usuario_id bigint, temporada text, posicao int, pontos numeric)")
            conn.execute("CREATE TABLE apostas(id bigint GENERATED ALWAYS AS IDENTITY, prova_id bigint, usuario_id bigint, temporada text, data_envio timestamptz DEFAULT now(), UNIQUE(prova_id, usuario_id, temporada))")
            conn.execute("CREATE INDEX ON provas(temporada, data)")
            conn.execute("CREATE INDEX ON posicoes_participantes(temporada, usuario_id, prova_id)")
            conn.execute("CREATE INDEX ON apostas(usuario_id, prova_id, temporada)")
            start_year = 2026 - args.seasons + 1
            race_id = 1
            for year in range(start_year, 2027):
                for race in range(args.races):
                    conn.execute("INSERT INTO provas VALUES(%s,%s,make_date(%s,1,1)+%s,%s)", (race_id, str(year), year, race * 7, f"GP {race + 1}"))
                    conn.execute("INSERT INTO posicoes_participantes SELECT %s, u, %s, u, (101-u)::numeric FROM generate_series(1,%s) u", (race_id, str(year), args.users))
                    conn.execute("INSERT INTO apostas(prova_id,usuario_id,temporada) SELECT %s,u,%s FROM generate_series(1,%s) u", (race_id, str(year), args.users))
                    race_id += 1
            conn.execute("ANALYZE")

            params = {"login": ("user1@example.test",), "painel": ("2026",), "classificacao": ("2026",), "historico": (1,)}
            for name, query in READS.items():
                samples = []
                for _ in range(args.iterations):
                    started = time.perf_counter()
                    conn.execute(query, params[name]).fetchall()
                    samples.append((time.perf_counter() - started) * 1000)
                explain = conn.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, params[name]).fetchone()[0]
                report["workloads"][name] = {"p50_ms": round(statistics.median(samples), 2), "p95_ms": round(percentile(samples, .95), 2), "explain": explain}

            bet_samples = []
            for user_id in range(args.users + 1, args.users + 1 + args.iterations):
                started = time.perf_counter()
                conn.execute("INSERT INTO apostas(prova_id,usuario_id,temporada) VALUES(%s,%s,%s) ON CONFLICT(prova_id,usuario_id,temporada) DO UPDATE SET data_envio=now()", (race_id - 1, user_id, "2026"))
                bet_samples.append((time.perf_counter() - started) * 1000)
            report["workloads"]["envio_aposta"] = {
                "p50_ms": round(statistics.median(bet_samples), 2),
                "p95_ms": round(percentile(bet_samples, .95), 2),
            }
            violations = []
            for workload, result in report["workloads"].items():
                target = 1500 if workload == "envio_aposta" else 1000
                if result["p95_ms"] >= target:
                    violations.append({"workload": workload, "p95_ms": result["p95_ms"], "target_ms": target})
            report["targets"] = {"read_p95_ms": 1000, "bet_submission_p95_ms": 1500, "violations": violations}
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        finally:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


if __name__ == "__main__":
    main()
