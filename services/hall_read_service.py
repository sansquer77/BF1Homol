"""Modelo de leitura do Hall da Fama para a V4."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from db.db_schema import db_connect
from services.hall_da_fama_controller import resolve_hall_source


def build_hall_of_fame() -> dict[str, Any]:
    with db_connect() as conn:
        source, _ = resolve_hall_source(conn)
        cursor = conn.cursor()
        if source == "posicoes_participantes":
            cursor.execute(
                """
                SELECT DISTINCT ON (pp.usuario_id, pp.temporada)
                       pp.temporada, pp.posicao AS position, pp.pontos, u.nome
                FROM posicoes_participantes pp
                JOIN usuarios u ON u.id = pp.usuario_id
                WHERE pp.temporada IS NOT NULL
                  AND trim(cast(pp.temporada AS text)) != ''
                  AND lower(coalesce(u.perfil, '')) != 'master'
                ORDER BY pp.usuario_id, pp.temporada, pp.prova_id DESC NULLS LAST, pp.id DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT hf.temporada, hf.posicao_final AS position, hf.pontos, u.nome
                FROM hall_da_fama hf
                JOIN usuarios u ON u.id = hf.usuario_id
                WHERE hf.temporada IS NOT NULL
                  AND trim(cast(hf.temporada AS text)) != ''
                  AND lower(coalesce(u.perfil, '')) != 'master'
                ORDER BY hf.temporada DESC, hf.posicao_final, u.nome
                """
            )
        rows = [dict(row) for row in (cursor.fetchall() or [])]
        cursor.close()

    return assemble_hall(rows, source)


def assemble_hall(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    normalized = []
    for row in rows:
        try:
            normalized.append({
                "season": str(row["temporada"]),
                "position": int(row["position"]),
                "points": float(row.get("pontos") or 0),
                "participant": str(row["nome"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    normalized.sort(key=lambda item: (-int(item["season"]) if item["season"].isdigit() else 0, item["position"], item["participant"]))

    seasons = sorted({item["season"] for item in normalized}, reverse=True)
    wins = Counter(item["participant"] for item in normalized if item["position"] == 1)
    season_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    position_groups: dict[str, Counter[int]] = defaultdict(Counter)
    for item in normalized:
        season_groups[item["season"]].append(item)
        position_groups[item["participant"]][item["position"]] += 1

    season_stats = []
    for season in seasons:
        entries = season_groups[season]
        points = [entry["points"] for entry in entries]
        champion = next((entry for entry in entries if entry["position"] == 1), None)
        season_stats.append({
            "season": season,
            "participants": len(entries),
            "best_points": max(points) if points else None,
            "average_points": round(sum(points) / len(points), 2) if points else None,
            "champion": champion,
        })

    distribution = [
        {"participant": participant, "positions": [{"position": position, "count": count} for position, count in sorted(counts.items())]}
        for participant, counts in sorted(position_groups.items())
    ]
    return {
        "source": source,
        "seasons": seasons,
        "entries": normalized,
        "top_winners": [{"participant": name, "wins": count} for name, count in sorted(wins.items(), key=lambda item: (-item[1], item[0]))[:3]],
        "season_stats": season_stats,
        "distribution": distribution,
    }


__all__ = ["assemble_hall", "build_hall_of_fame"]
