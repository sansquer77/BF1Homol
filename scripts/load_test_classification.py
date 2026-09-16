"""Teste controlado de concorrência da Classificação V4 em homologação."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import math
import os
import statistics
import time

import httpx


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(percentile_value * len(ordered)) - 1))
    return ordered[index]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--season", default="2026")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default="load-test-classification.json")
    args = parser.parse_args()
    email = os.environ.get("BF1_LOAD_EMAIL", "")
    password = os.environ.get("BF1_LOAD_PASSWORD", "")
    if not email or not password:
        raise SystemExit("BF1_LOAD_EMAIL e BF1_LOAD_PASSWORD são obrigatórios")

    base_url = args.base_url.rstrip("/")
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers={"Origin": base_url},
        )
        if login.status_code != 200:
            raise SystemExit(f"Login recusado: HTTP {login.status_code}")

        warmup = await client.get(f"/api/v1/classification?season={args.season}")
        if warmup.status_code != 200:
            raise SystemExit(f"Warm-up recusado: HTTP {warmup.status_code}")

        gate = asyncio.Event()

        async def virtual_user(_: int) -> list[dict]:
            await gate.wait()
            samples = []
            for _iteration in range(args.iterations):
                started = time.perf_counter()
                try:
                    response = await client.get(f"/api/v1/classification?season={args.season}")
                    samples.append({
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "bytes": len(response.content),
                    })
                except Exception as exc:
                    samples.append({
                        "status": 0,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "error": type(exc).__name__,
                        "bytes": 0,
                    })
            return samples

        tasks = [asyncio.create_task(virtual_user(index)) for index in range(args.users)]
        started = time.perf_counter()
        gate.set()
        nested = await asyncio.gather(*tasks)
        wall_seconds = time.perf_counter() - started
        samples = [sample for group in nested for sample in group]
        durations = [sample["duration_ms"] for sample in samples]
        failures = [sample for sample in samples if sample["status"] != 200]
        error_counts = Counter(
            sample["error"] for sample in failures if sample.get("error")
        )
        report = {
            "target": f"{base_url}/api/v1/classification?season={args.season}",
            "virtual_users": args.users,
            "iterations_per_user": args.iterations,
            "requests": len(samples),
            "wall_seconds": round(wall_seconds, 3),
            "requests_per_second": round(len(samples) / wall_seconds, 3),
            "failures": len(failures),
            "error_rate": round(len(failures) / len(samples), 6),
            "latency_ms": {
                "min": round(min(durations), 3),
                "mean": round(statistics.fmean(durations), 3),
                "p50": round(percentile(durations, 0.50), 3),
                "p95": round(percentile(durations, 0.95), 3),
                "p99": round(percentile(durations, 0.99), 3),
                "max": round(max(durations), 3),
            },
            "status_counts": {
                str(status): sum(1 for sample in samples if sample["status"] == status)
                for status in sorted({sample["status"] for sample in samples})
            },
            "client_error_counts": dict(sorted(error_counts.items())),
        }
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
