"""Utilitarios para base de circuitos F1 (Ergast/Jolpica)."""

from __future__ import annotations

import json
import logging
from typing import Iterable

import requests

from db.db_utils import db_connect

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
REQUEST_TIMEOUT = 12


def ensure_circuitos_f1_table() -> None:
    """Cria a tabela base de circuitos quando ausente."""
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS circuitos_f1 (
                circuit_id TEXT PRIMARY KEY,
                circuit_name TEXT NOT NULL,
                country TEXT,
                locality TEXT,
                aliases TEXT,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_circuitos_f1_country ON circuitos_f1(country)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_circuitos_f1_locality ON circuitos_f1(locality)")
        conn.commit()


def ensure_provas_circuit_id_column() -> None:
    """Garante coluna circuit_id em provas, sem quebrar bancos legados."""
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('provas')")
        cols = [r[1] for r in c.fetchall()]
        if "circuit_id" not in cols:
            c.execute("ALTER TABLE provas ADD COLUMN circuit_id TEXT REFERENCES circuitos_f1(circuit_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_provas_circuit_id ON provas(circuit_id)")
        conn.commit()


def _extract_circuit_entries_from_season(data: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        races = data["MRData"]["RaceTable"].get("Races", [])
    except (KeyError, TypeError):
        races = []

    for race in races:
        circuit = race.get("Circuit", {})
        location = circuit.get("Location", {})
        circuit_id = str(circuit.get("circuitId", "")).strip()
        if not circuit_id:
            continue

        race_name = str(race.get("raceName", "")).strip()
        circuit_name = str(circuit.get("circuitName", "")).strip() or race_name or circuit_id
        locality = str(location.get("locality", "")).strip() or None
        country = str(location.get("country", "")).strip() or None

        aliases = {
            race_name,
            circuit_name,
            locality or "",
            country or "",
        }
        aliases_clean = sorted({a for a in aliases if a})

        existing = out.get(circuit_id)
        if existing is None:
            out[circuit_id] = {
                "circuit_name": circuit_name,
                "country": country,
                "locality": locality,
                "aliases": aliases_clean,
            }
        else:
            # Mantem circuito e agrega aliases entre chamadas/temporadas.
            existing_aliases = set(existing.get("aliases", []))
            existing_aliases.update(aliases_clean)
            existing["aliases"] = sorted(existing_aliases)
            if not existing.get("circuit_name") and circuit_name:
                existing["circuit_name"] = circuit_name
            if not existing.get("country") and country:
                existing["country"] = country
            if not existing.get("locality") and locality:
                existing["locality"] = locality

    return out


def _fetch_season_json(season: str) -> dict | None:
    url = f"{BASE_URL}/{season}.json"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("Falha ao consultar Ergast/Jolpica para temporada %s: %s", season, e)
        return None


def atualizar_base_circuitos(seasons: Iterable[str]) -> dict[str, int]:
    """Atualiza tabela circuitos_f1 a partir das temporadas informadas.

    Retorna contagem de temporadas processadas e circuitos upsertados.
    """
    ensure_circuitos_f1_table()

    seasons_norm = sorted({str(s).strip() for s in seasons if str(s).strip()})
    if not seasons_norm:
        return {"temporadas": 0, "circuitos": 0}

    merged: dict[str, dict] = {}
    processed = 0

    for season in seasons_norm:
        data = _fetch_season_json(season)
        if not data:
            continue
        processed += 1
        entries = _extract_circuit_entries_from_season(data)
        for circuit_id, item in entries.items():
            if circuit_id not in merged:
                merged[circuit_id] = item
            else:
                old = merged[circuit_id]
                aliases = set(old.get("aliases", []))
                aliases.update(item.get("aliases", []))
                old["aliases"] = sorted(aliases)
                if not old.get("circuit_name") and item.get("circuit_name"):
                    old["circuit_name"] = item["circuit_name"]
                if not old.get("country") and item.get("country"):
                    old["country"] = item["country"]
                if not old.get("locality") and item.get("locality"):
                    old["locality"] = item["locality"]

    if not merged:
        return {"temporadas": processed, "circuitos": 0}

    with db_connect() as conn:
        c = conn.cursor()
        for circuit_id, item in merged.items():
            c.execute(
                """
                INSERT INTO circuitos_f1 (circuit_id, circuit_name, country, locality, aliases, atualizado_em)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(circuit_id) DO UPDATE SET
                    circuit_name = excluded.circuit_name,
                    country = excluded.country,
                    locality = excluded.locality,
                    aliases = excluded.aliases,
                    atualizado_em = CURRENT_TIMESTAMP
                """,
                (
                    circuit_id,
                    str(item.get("circuit_name") or circuit_id),
                    item.get("country"),
                    item.get("locality"),
                    json.dumps(item.get("aliases", []), ensure_ascii=False),
                ),
            )
        conn.commit()

    logger.info("✓ Base de circuitos atualizada: %s temporadas, %s circuitos", processed, len(merged))
    return {"temporadas": processed, "circuitos": len(merged)}


def get_circuitos_df():
    """Retorna DataFrame de circuitos para uso em UI."""
    import pandas as pd

    ensure_circuitos_f1_table()
    with db_connect() as conn:
        return pd.read_sql_query(
            """
            SELECT circuit_id, circuit_name, country, locality, aliases, atualizado_em
            FROM circuitos_f1
            ORDER BY circuit_name ASC
            """,
            conn,
        )


def get_temporadas_existentes_provas() -> list[str]:
    """Lista temporadas existentes na tabela provas (fallback para ano atual)."""
    from datetime import datetime

    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('provas')")
        cols = [r[1] for r in c.fetchall()]
        if "temporada" not in cols:
            return [str(datetime.now().year)]

        c.execute("SELECT DISTINCT temporada FROM provas WHERE temporada IS NOT NULL AND TRIM(temporada) <> '' ORDER BY temporada")
        rows = [str(r[0]).strip() for r in c.fetchall() if r and r[0]]
        return rows or [str(datetime.now().year)]
