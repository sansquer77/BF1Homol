"""Recursos de IA/contexto para geração automática de apostas."""

from __future__ import annotations

import ast
import importlib
import json
import logging
import os
from typing import Optional

import pandas as pd

from utils.data_utils import (
    get_circuit_id_por_nome_prova,
    get_constructor_standings,
    get_driver_standings,
    get_fastest_lap_times,
    get_frequencia_11_por_piloto,
    get_historico_circuito,
    get_posicoes_recentes,
    get_qualifying_grid_ultima_corrida,
    get_qualifying_vs_race_delta,
    get_taxa_dnf_por_piloto,
)
from utils.data_utils import get_current_season

logger = logging.getLogger(__name__)
MAX_PERPLEXITY_CONTEXT_CHARS = 5200

try:
    httpx = importlib.import_module("httpx")
except ImportError:
    httpx = None


def _extrair_json_texto(raw_text: str) -> Optional[dict]:
    if not raw_text:
        return None
    txt = raw_text.strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    ini = txt.find("{")
    fim = txt.rfind("}")
    if ini == -1 or fim == -1 or fim <= ini:
        return None
    try:
        return json.loads(txt[ini : fim + 1])
    except Exception:
        return None


def _get_resumo_ultimas_apostas(usuario_id: int, apostas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if apostas_df.empty:
        return []
    ap = apostas_df[apostas_df["usuario_id"] == usuario_id].copy()
    if ap.empty:
        return []
    if "data_envio" in ap.columns:
        ap["__envio"] = pd.to_datetime(ap["data_envio"], errors="coerce")
        ap = ap.sort_values(by=["__envio"])
    ap = ap.drop_duplicates(subset=["prova_id"], keep="last")
    ap = ap.sort_values(by=["prova_id"], ascending=False).head(limite)

    out = []
    for _, row in ap.iterrows():
        try:
            fichas = [int(x) for x in str(row.get("fichas", "")).split(",") if str(x).strip() != ""]
        except Exception:
            fichas = []
        out.append(
            {
                "pilotos": [p.strip() for p in str(row.get("pilotos", "")).split(",") if p.strip()],
                "fichas": fichas,
                "piloto_11": str(row.get("piloto_11", "")).strip(),
            }
        )
    return out


def _get_resumo_cenario_campeonato(resultados_df: pd.DataFrame, provas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if resultados_df.empty:
        return []
    res = resultados_df.copy()
    if "prova_id" in res.columns:
        res = res.sort_values(by=["prova_id"], ascending=False).head(limite)

    provas_nome = {}
    if not provas_df.empty and "id" in provas_df.columns and "nome" in provas_df.columns:
        provas_nome = dict(zip(provas_df["id"], provas_df["nome"]))

    out = []
    for _, row in res.iterrows():
        posicoes = {}
        try:
            posicoes = ast.literal_eval(str(row.get("posicoes", "{}")))
            if not isinstance(posicoes, dict):
                posicoes = {}
        except Exception:
            posicoes = {}
        top3 = [str(posicoes.get(i, "")).strip() for i in [1, 2, 3]]
        out.append(
            {
                "prova": str(provas_nome.get(row.get("prova_id"), f"Prova {row.get('prova_id')}")),
                "top3": [p for p in top3 if p],
            }
        )
    return out


def _get_contexto_temporada_atual_ergast(temporada: Optional[str] = None, nome_prova: Optional[str] = None) -> dict:
    contexto = {
        "src": "ergast",
        "s": None,
        "tp": [],
        "tc": [],
        "du": {"top": [], "bot": []},
        "vr": [],
        "qg": {},
        "rp5": {},
        "rp8": {},
        "hc": {},
        "fr11": {},
        "dnf": {},
        "circuit_id": None,
    }

    try:
        temporada_resolvida = str(temporada or get_current_season())
    except Exception:
        temporada_resolvida = "current"

    contexto["s"] = temporada_resolvida

    try:
        df_pilotos = get_driver_standings(temporada_resolvida)
        if not df_pilotos.empty:
            top_pilotos = []
            for _, row in df_pilotos.head(8).iterrows():
                top_pilotos.append(
                    {
                        "p": int(row.get("Position", 0) or 0),
                        "n": str(row.get("Driver", "")).strip(),
                        "e": str(row.get("Constructor", "")).strip(),
                        "pt": int(row.get("Points", 0) or 0),
                    }
                )
            contexto["tp"] = top_pilotos
    except Exception:
        pass

    try:
        df_construtores = get_constructor_standings(temporada_resolvida)
        if not df_construtores.empty:
            top_construtores = []
            for _, row in df_construtores.head(5).iterrows():
                top_construtores.append(
                    {
                        "p": int(row.get("Position", 0) or 0),
                        "n": str(row.get("Constructor", "")).strip(),
                        "pt": int(row.get("Points", 0) or 0),
                    }
                )
            contexto["tc"] = top_construtores
    except Exception:
        pass

    try:
        df_delta = get_qualifying_vs_race_delta(temporada_resolvida)
        if not df_delta.empty:
            top_delta = []
            bottom_delta = []
            for _, row in df_delta.sort_values("Delta", ascending=False).head(5).iterrows():
                top_delta.append(
                    {
                        "n": str(row.get("Driver", "")).strip(),
                        "d": int(row.get("Delta", 0) or 0),
                    }
                )
            for _, row in df_delta.sort_values("Delta", ascending=True).head(4).iterrows():
                bottom_delta.append(
                    {
                        "n": str(row.get("Driver", "")).strip(),
                        "d": int(row.get("Delta", 0) or 0),
                    }
                )
            contexto["du"] = {"top": top_delta, "bot": bottom_delta}
    except Exception:
        pass

    try:
        df_volta_rapida = get_fastest_lap_times(temporada_resolvida)
        if not df_volta_rapida.empty:
            voltas = []
            for _, row in df_volta_rapida.head(5).iterrows():
                voltas.append({"n": str(row.get("Driver", "")).strip(), "t": str(row.get("Fastest Lap", "")).strip()})
            contexto["vr"] = voltas
    except Exception:
        pass

    try:
        contexto["qg"] = get_qualifying_grid_ultima_corrida(temporada_resolvida)
    except Exception:
        pass

    try:
        contexto["rp5"] = get_posicoes_recentes(temporada_resolvida, n_corridas=5)
    except Exception:
        pass

    try:
        contexto["rp8"] = get_posicoes_recentes(temporada_resolvida, n_corridas=8)
    except Exception:
        pass

    try:
        contexto["dnf"] = get_taxa_dnf_por_piloto(temporada_resolvida, n_corridas=8)
    except Exception:
        pass

    try:
        ano = int(temporada_resolvida)
        seasons_11 = [str(ano - 2), str(ano - 1), str(ano)]
    except Exception:
        seasons_11 = None

    try:
        contexto["fr11"] = get_frequencia_11_por_piloto(seasons_11)
    except Exception:
        pass

    try:
        if nome_prova:
            circuit_id = get_circuit_id_por_nome_prova(temporada_resolvida, nome_prova)
            if circuit_id:
                contexto["circuit_id"] = circuit_id
                contexto["hc"] = get_historico_circuito(circuit_id, n_anos=4, season_ref=temporada_resolvida)
    except Exception:
        pass

    return contexto


def _canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _reduce_context_for_limit(data: dict) -> dict:
    d = dict(data)
    erg = dict(d.get("erg", {}))
    if "vr" in erg:
        erg = dict(erg)
        erg["vr"] = []
        d["erg"] = erg

    if "ua" in d:
        d["ua"] = d.get("ua", [])[:1]
    if "cz" in d:
        d["cz"] = d.get("cz", [])[:1]

    erg2 = dict(d.get("erg", {}))
    if "tp" in erg2:
        erg2["tp"] = erg2.get("tp", [])[:3]
    if "tc" in erg2:
        erg2["tc"] = erg2.get("tc", [])[:2]
    du = dict(erg2.get("du", {}))
    if du:
        du["top"] = du.get("top", [])[:2]
        du["bot"] = du.get("bot", [])[:1]
        erg2["du"] = du
    d["erg"] = erg2
    return d


def _minimal_context_for_limit(data: dict) -> dict:
    erg = dict(data.get("erg", {}))
    du = dict(erg.get("du", {}))
    return {
        "v": data.get("v", 1),
        "alvo": data.get("alvo", {}),
        "pd": data.get("pd", []),
        "rg": data.get("rg", {}),
        "ua": data.get("ua", [])[:1],
        "cz": data.get("cz", [])[:1],
        "erg": {
            "src": erg.get("src", "ergast"),
            "s": erg.get("s"),
            "tp": erg.get("tp", [])[:3],
            "tc": erg.get("tc", [])[:2],
            "du": {"top": du.get("top", [])[:2], "bot": du.get("bot", [])[:1]},
            "vr": [],
        },
    }


def _build_compact_json_with_meta(payload_data: dict) -> tuple[str, str]:
    compact = _canonical_json(payload_data)
    if len(compact) <= MAX_PERPLEXITY_CONTEXT_CHARS:
        return compact, "none"

    reduced = _reduce_context_for_limit(payload_data)
    compact_reduced = _canonical_json(reduced)
    if len(compact_reduced) <= MAX_PERPLEXITY_CONTEXT_CHARS:
        return compact_reduced, "reduced"

    minimal = _minimal_context_for_limit(payload_data)
    return _canonical_json(minimal), "minimal"


def _build_compact_prompt_payload(
    nome_prova: str,
    tipo_prova: str,
    pilotos_disponiveis: list[str],
    min_pilotos: int,
    qtd_fichas: int,
    fichas_max: int,
    permite_mesma_equipe: bool,
    ultimas_apostas: list[dict],
    cenario: list[dict],
    contexto_ergast: dict,
) -> tuple[str, str]:
    payload_data = {
        "v": 1,
        "alvo": {"nome": nome_prova, "tipo": tipo_prova},
        "pd": pilotos_disponiveis,
        "rg": {"min": min_pilotos, "qf": qtd_fichas, "fmax": fichas_max, "me": permite_mesma_equipe},
        "ua": ultimas_apostas,
        "cz": cenario,
        "erg": contexto_ergast,
    }
    return _build_compact_json_with_meta(payload_data)


def _validar_formato_json_resposta(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return False
    expected = {"pilotos", "fichas", "piloto_11"}
    if set(parsed.keys()) != expected:
        return False
    pilotos = parsed.get("pilotos")
    fichas = parsed.get("fichas")
    piloto_11 = parsed.get("piloto_11")
    if not isinstance(pilotos, list) or not isinstance(fichas, list) or not isinstance(piloto_11, str):
        return False
    if len(pilotos) == 0 or len(fichas) == 0 or len(pilotos) != len(fichas):
        return False
    try:
        _ = [str(p).strip() for p in pilotos]
        _ = [int(x) for x in fichas]
    except Exception:
        return False
    return piloto_11.strip() != ""


def _gerar_aposta_perplexity(
    pilotos_df: pd.DataFrame,
    regras: dict,
    nome_prova: str,
    tipo_prova: str,
    ultimas_apostas: list[dict],
    cenario: list[dict],
    contexto_ergast: dict,
) -> Optional[tuple[list[str], list[int], str]]:
    if httpx is None:
        return None

    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    model = os.environ.get("PERPLEXITY_MODEL", "sonar")
    if not api_key:
        return None

    pilotos_disponiveis = [str(x) for x in pilotos_df["nome"].tolist()] if not pilotos_df.empty else []
    min_pilotos = int(regras.get("qtd_minima_pilotos") or regras.get("min_pilotos", 3))
    qtd_fichas = int(regras.get("quantidade_fichas", 15))
    fichas_max = int(regras.get("fichas_por_piloto", qtd_fichas))
    permite_mesma_equipe = bool(regras.get("mesma_equipe", False))

    contexto_compacto_json, context_fallback_mode = _build_compact_prompt_payload(
        nome_prova=nome_prova,
        tipo_prova=tipo_prova,
        pilotos_disponiveis=pilotos_disponiveis,
        min_pilotos=min_pilotos,
        qtd_fichas=qtd_fichas,
        fichas_max=fichas_max,
        permite_mesma_equipe=permite_mesma_equipe,
        ultimas_apostas=ultimas_apostas,
        cenario=cenario,
        contexto_ergast=contexto_ergast,
    )
    logger.debug(
        "Perplexity payload context size=%d fallback=%s limit=%d",
        len(contexto_compacto_json),
        context_fallback_mode,
        MAX_PERPLEXITY_CONTEXT_CHARS,
    )

    system_prompt = (
        "Você é um assistente de estratégia de bolão de F1. "
        "Responda apenas JSON válido, sem markdown. "
        "Não invente pilotos fora da lista disponível. "
        "Se houver incerteza, faça uma aposta conservadora e viável. "
        "Use criatividade controlada: varie escolhas e distribuição entre chamadas quando houver alternativas plausíveis, "
        "mas evite sugestões irreais. "
        "Priorize pilotos de melhor desempenho recente/classificação e só assuma risco moderado. "
        "Evite concentrar muitas fichas em pilotos de baixo desempenho. "
        "Legenda das chaves do JSON de entrada: "
        "alvo={nome,tipo}, pd=pilotos_disponiveis, rg={min,qf,fmax,me}, ua=ultimas_apostas, cz=cenario_local, "
        "erg={src,s,tp,tc,du,vr}, tp={p,n,e,pt}, tc={p,n,pt}, du={top,bot}."
    )
    user_prompt = (
        "Dados de entrada (JSON canônico compacto):\n"
        f"{contexto_compacto_json}\n"
        "Gere uma aposta viável com este formato JSON EXATO: "
        "{\"pilotos\": [\"Nome\"], \"fichas\": [1,2], \"piloto_11\": \"Nome\"}."
    )

    payload = {
        "model": model,
        "temperature": 0.35,
        "max_tokens": 260,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extrair_json_texto(content)
        if not parsed:
            return None
        if not _validar_formato_json_resposta(parsed):
            return None
        pilotos = [str(p).strip() for p in parsed.get("pilotos", []) if str(p).strip()]
        fichas = [int(x) for x in parsed.get("fichas", [])]
        piloto_11 = str(parsed.get("piloto_11", "")).strip()
        if not pilotos or not fichas or not piloto_11:
            return None
        return pilotos, fichas, piloto_11
    except Exception as e:
        logger.warning("Falha na geração via Perplexity para aposta estratégica: %s", e)
        return None


__all__ = [
    "_extrair_json_texto",
    "_get_resumo_ultimas_apostas",
    "_get_resumo_cenario_campeonato",
    "_get_contexto_temporada_atual_ergast",
    "_gerar_aposta_perplexity",
]
