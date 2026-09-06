#!/usr/bin/env python3
"""Agrega eventos JSON do logger bf1.performance em uma linha de base."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]


def iter_events(lines: Iterable[str]):
    for line in lines:
        candidate = line.strip()
        if "{" in candidate:
            candidate = candidate[candidate.find("{"):]
        try:
            event = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if event.get("event") == "journey_performance":
            yield event


def aggregate(events: Iterable[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        grouped[str(event.get("journey", "unknown"))].append(event)
    journeys = {}
    for name, samples in sorted(grouped.items()):
        durations = [float(item.get("duration_ms", 0)) for item in samples]
        hits = sum(int(item.get("cache_hits", 0)) for item in samples)
        misses = sum(int(item.get("cache_misses", 0)) for item in samples)
        cache_total = hits + misses
        journeys[name] = {
            "samples": len(samples),
            "p50_ms": round(statistics.median(durations), 2),
            "p95_ms": round(percentile(durations, .95), 2),
            "avg_query_count": round(statistics.mean(float(item.get("query_count", 0)) for item in samples), 2),
            "avg_db_time_ms": round(statistics.mean(float(item.get("db_time_ms", 0)) for item in samples), 2),
            "avg_rows_fetched": round(statistics.mean(float(item.get("rows_fetched", 0)) for item in samples), 2),
            "avg_rows_processed": round(statistics.mean(float(item.get("rows_processed", 0)) for item in samples), 2),
            "cache_hit_rate": round(hits / cache_total, 4) if cache_total else None,
            "success_rate": round(sum(bool(item.get("success")) for item in samples) / len(samples), 4),
        }
    return {"event_count": sum(len(items) for items in grouped.values()), "journeys": journeys}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="Arquivo de log; omita para stdin")
    args = parser.parse_args()
    if args.path:
        with Path(args.path).open(encoding="utf-8", errors="replace") as stream:
            report = aggregate(iter_events(stream))
    else:
        report = aggregate(iter_events(sys.stdin))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
