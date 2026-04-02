"""Controller de regras de negócio do painel de participante."""

import datetime
import re

import pandas as pd

from utils.datetime_utils import now_sao_paulo, parse_datetime_sao_paulo


def parse_data_prova(data_raw):
    """Parse tolerante para datas de prova (yyyy-mm-dd e formatos locais)."""
    if data_raw is None:
        return None
    raw = str(data_raw).strip()
    if not raw:
        return None

    formatos_explicitos = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    )
    for formato in formatos_explicitos:
        parsed = pd.to_datetime(raw, format=formato, errors="coerce")
        if pd.notna(parsed):
            return parsed

    usa_dayfirst = bool(re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$", raw))
    parsed = pd.to_datetime(raw, errors="coerce", dayfirst=usa_dayfirst)
    if pd.notna(parsed):
        return parsed
    return None


def parse_evento_prova_dt(data_raw, hora_raw, tzinfo):
    data_dt = parse_data_prova(data_raw)
    if data_dt is None:
        return None

    data_iso = data_dt.strftime("%Y-%m-%d")
    hora = str(hora_raw or "00:00")
    try:
        return parse_datetime_sao_paulo(data_iso, hora)
    except Exception:
        return datetime.datetime(
            data_dt.year,
            data_dt.month,
            data_dt.day,
            0,
            0,
            tzinfo=tzinfo,
        )


def get_proxima_prova_id(provas_df: pd.DataFrame):
    """Retorna o ID da próxima prova (data/hora >= agora em Sao Paulo)."""
    if provas_df.empty or "id" not in provas_df.columns:
        return None

    agora_sp = now_sao_paulo()
    tzinfo = agora_sp.tzinfo

    futuras: list[tuple[datetime.datetime, int]] = []
    passadas: list[tuple[datetime.datetime, int]] = []
    for _, row in provas_df.iterrows():
        prova_id = row.get("id")
        if prova_id is None or not row.get("data"):
            continue
        evento_dt = parse_evento_prova_dt(row.get("data"), row.get("horario_prova", "00:00"), tzinfo)
        if evento_dt is None:
            continue
        if evento_dt >= agora_sp:
            futuras.append((evento_dt, int(prova_id)))
        else:
            passadas.append((evento_dt, int(prova_id)))

    if futuras:
        return min(futuras, key=lambda x: x[0])[1]
    if passadas:
        return max(passadas, key=lambda x: x[0])[1]
    return None


def ordenar_provas_por_calendario(provas_df: pd.DataFrame) -> pd.DataFrame:
    """Ordena provas por data/hora do calendário (ascendente), com fallback estável."""
    if provas_df.empty:
        return provas_df

    ordered = provas_df.copy()
    tzinfo = now_sao_paulo().tzinfo

    if "data" in ordered.columns:
        ordered["__data_dt"] = ordered["data"].apply(parse_data_prova)
        ordered["__evento_dt"] = ordered.apply(
            lambda row: parse_evento_prova_dt(
                row.get("data"),
                row.get("horario_prova", "00:00"),
                tzinfo,
            ),
            axis=1,
        )
    else:
        ordered["__data_dt"] = pd.NaT
        ordered["__evento_dt"] = pd.NaT

    ordered = ordered.sort_values(
        by=["__evento_dt", "__data_dt", "id"],
        na_position="last",
    ).reset_index(drop=True)

    return ordered


__all__ = [
    "parse_data_prova",
    "parse_evento_prova_dt",
    "get_proxima_prova_id",
    "ordenar_provas_por_calendario",
]
