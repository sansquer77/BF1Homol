import pandas as pd
import logging
import os
import json
import ast
import math
import hashlib
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Optional, Union, cast
from db.db_utils import (
    get_table_columns,
    get_user_by_id,
    get_horario_prova,
    db_connect,
    get_pilotos_df,
    registrar_log_aposta,
    log_aposta_existe,
    get_apostas_df,
    get_provas_df,
    get_resultados_df
)
from services.email_service import enviar_email, gerar_analise_aposta_com_probabilidade
import html
from services.rules_service import get_regras_aplicaveis
from utils.data_utils import (
    get_current_season,
    get_driver_standings,
    get_constructor_standings,
    get_qualifying_vs_race_delta,
    get_fastest_lap_times,
    get_posicoes_recentes,
    get_historico_circuito,
    get_frequencia_11_por_piloto,
    get_taxa_dnf_por_piloto,
    get_qualifying_grid_ultima_corrida,
    get_circuit_id_por_nome_prova,
)
from utils.datetime_utils import SAO_PAULO_TZ, now_sao_paulo, parse_datetime_sao_paulo
from utils.request_utils import get_client_ip
from utils.input_models import BetSubmissionInput, ValidationError
from utils.logging_utils import redact_identifier

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
    ini = txt.find('{')
    fim = txt.rfind('}')
    if ini == -1 or fim == -1 or fim <= ini:
        return None
    try:
        return json.loads(txt[ini:fim + 1])
    except Exception:
        return None


def _aposta_valida_regras(pilotos_sel: list[str], fichas_sel: list[int], piloto_11: str, pilotos_df: pd.DataFrame, regras: dict) -> bool:
    if not pilotos_sel or not fichas_sel or not piloto_11:
        return False

    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

    if len(pilotos_sel) < min_pilotos:
        return False
    if len(pilotos_sel) != len(fichas_sel):
        return False
    if len(set(pilotos_sel)) != len(pilotos_sel):
        return False
    if sum(int(f) for f in fichas_sel) != qtd_fichas:
        return False
    if fichas_sel and max(int(f) for f in fichas_sel) > fichas_max:
        return False
    if piloto_11 in pilotos_sel:
        return False

    pilotos_disponiveis = set(pilotos_df['nome'].astype(str).tolist()) if not pilotos_df.empty else set()
    if pilotos_disponiveis and any(str(p) not in pilotos_disponiveis for p in pilotos_sel):
        return False
    if pilotos_disponiveis and str(piloto_11) not in pilotos_disponiveis:
        return False

    if not permite_mesma_equipe and not pilotos_df.empty and 'equipe' in pilotos_df.columns:
        mapa_eq: dict[str, str] = {
            str(nome): str(eq)
            for nome, eq in zip(pilotos_df['nome'].astype(str), pilotos_df['equipe'].astype(str))
        }
        equipes = [mapa_eq.get(str(p), '') for p in pilotos_sel]
        equipes_validas = [e for e in equipes if e]
        if len(set(equipes_validas)) < len(equipes_validas):
            return False

    return True


def _get_resumo_ultimas_apostas(usuario_id: int, apostas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if apostas_df.empty:
        return []
    ap = cast(pd.DataFrame, apostas_df[apostas_df['usuario_id'] == usuario_id].copy())
    if ap.empty:
        return []
    if 'data_envio' in ap.columns:
        ap['__envio'] = pd.to_datetime(ap['data_envio'], errors='coerce')
        ap = ap.sort_values(by=['__envio'])
    ap = ap.drop_duplicates(subset=['prova_id'], keep='last')
    ap = ap.sort_values(by=['prova_id'], ascending=False).head(limite)

    out = []
    for _, row in ap.iterrows():
        try:
            fichas = [int(x) for x in str(row.get('fichas', '')).split(',') if str(x).strip() != '']
        except Exception:
            fichas = []
        out.append({
            'pilotos': [p.strip() for p in str(row.get('pilotos', '')).split(',') if p.strip()],
            'fichas': fichas,
            'piloto_11': str(row.get('piloto_11', '')).strip()
        })
    return out


def _get_resumo_cenario_campeonato(resultados_df: pd.DataFrame, provas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if resultados_df.empty:
        return []
    res = cast(pd.DataFrame, resultados_df.copy())
    if 'prova_id' in res.columns:
        res = res.sort_values(by=['prova_id'], ascending=False).head(limite)

    provas_nome = {}
    if not provas_df.empty and 'id' in provas_df.columns and 'nome' in provas_df.columns:
        provas_nome = dict(zip(provas_df['id'], provas_df['nome']))

    out = []
    for _, row in res.iterrows():
        posicoes = {}
        try:
            posicoes = ast.literal_eval(str(row.get('posicoes', '{}')))
            if not isinstance(posicoes, dict):
                posicoes = {}
        except Exception:
            posicoes = {}
        top3 = [str(posicoes.get(i, '')).strip() for i in [1, 2, 3]]
        out.append({
            'prova': str(provas_nome.get(row.get('prova_id'), f"Prova {row.get('prova_id')}")),
            'top3': [p for p in top3 if p]
        })
    return out


def _get_contexto_temporada_atual_ergast(temporada: Optional[str] = None, nome_prova: Optional[str] = None) -> dict:
    """Monta resumo normalizado e compacto da temporada com sinais avançados da Ergast/Jolpica."""
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
                voltas.append(
                    {
                        "n": str(row.get("Driver", "")).strip(),
                        "t": str(row.get("Fastest Lap", "")).strip(),
                    }
                )
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


def _norm_nome_piloto(nome: str) -> str:
    return str(nome or "").strip().lower()


def _media_lista(nums: list[int]) -> Optional[float]:
    if not nums:
        return None
    return float(sum(nums)) / float(len(nums))


def _desvio_padrao_populacao(nums: list[int]) -> Optional[float]:
    if len(nums) < 2:
        return None
    m = float(sum(nums)) / float(len(nums))
    var = sum((float(x) - m) ** 2 for x in nums) / float(len(nums))
    return math.sqrt(var)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _estimar_pontos_aposta_ergast(
    pilotos: list[str],
    fichas: list[int],
    piloto_11: str,
    tipo_prova: str,
    regras: dict,
    contexto_ergast: dict,
) -> dict:
    """Estima pontos usando alocação de posições mais prováveis sem duplicidade.

    Regra aplicada:
    - monta distribuição de probabilidade por piloto para cada posição pontuável
    - escolhe uma posição única por piloto (sem duas apostas na mesma posição)
    - calcula pontos estimados com a posição escolhida * fichas
    - calcula probabilidade combinada de acerto a partir das probabilidades escolhidas
    """
    pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]

    is_sprint = str(tipo_prova).strip().lower() == "sprint"
    if is_sprint:
        pontos_lista = regras.get("pontos_sprint_posicoes") or regras.get("pontos_posicoes") or pontos_sprint
    else:
        pontos_lista = regras.get("pontos_posicoes") or pontos_f1

    tp = contexto_ergast.get("tp", []) if isinstance(contexto_ergast, dict) else []
    du = contexto_ergast.get("du", {}) if isinstance(contexto_ergast, dict) else {}
    vr = contexto_ergast.get("vr", []) if isinstance(contexto_ergast, dict) else []

    qg = contexto_ergast.get("qg", {}) if isinstance(contexto_ergast, dict) else {}
    rp5 = contexto_ergast.get("rp5", {}) if isinstance(contexto_ergast, dict) else {}
    rp8 = contexto_ergast.get("rp8", {}) if isinstance(contexto_ergast, dict) else {}
    hc = contexto_ergast.get("hc", {}) if isinstance(contexto_ergast, dict) else {}
    fr11 = contexto_ergast.get("fr11", {}) if isinstance(contexto_ergast, dict) else {}
    dnf = contexto_ergast.get("dnf", {}) if isinstance(contexto_ergast, dict) else {}

    pos_por_nome: dict[str, int] = {}
    for row in tp if isinstance(tp, list) else []:
        nome = _norm_nome_piloto(row.get("n"))
        pos = int(row.get("p", 0) or 0)
        if nome and pos > 0:
            pos_por_nome[nome] = pos

    delta_por_nome: dict[str, int] = {}
    if isinstance(du, dict):
        for row in du.get("top", []) if isinstance(du.get("top", []), list) else []:
            nome = _norm_nome_piloto(row.get("n"))
            delta_por_nome[nome] = int(row.get("d", 0) or 0)
        for row in du.get("bot", []) if isinstance(du.get("bot", []), list) else []:
            nome = _norm_nome_piloto(row.get("n"))
            delta_por_nome[nome] = int(row.get("d", 0) or 0)

    vr_set = {
        _norm_nome_piloto(row.get("n"))
        for row in vr if isinstance(vr, list)
        if _norm_nome_piloto(row.get("n"))
    }

    # Prepara pilotos válidos (fichas > 0)
    pilotos_validos: list[tuple[str, int]] = []
    for piloto, ficha in zip(pilotos, fichas):
        try:
            ficha_i = int(ficha)
        except Exception:
            ficha_i = 0
        if ficha_i > 0:
            pilotos_validos.append((piloto, ficha_i))

    n_pos = len(pontos_lista)
    if not pilotos_validos or n_pos <= 0:
        return {
            "pontos_estimados": 0.0,
            "bonus_11_estimado": 0.0,
            "chance_11": 0,
            "probabilidade_combinada": 0,
            "criterios": "Ergast(tp/du/vr) + regras da prova",
            "detalhes": "Sem dados suficientes para estimativa.",
        }

    # Matriz de probabilidade por piloto/posição (1..n_pos)
    prob_por_piloto: list[list[float]] = []
    for piloto, _ in pilotos_validos:
        nome_key = _norm_nome_piloto(piloto)
        base_rank = pos_por_nome.get(nome_key)
        delta = int(delta_por_nome.get(nome_key, 0))
        ajuste_vr = -0.6 if nome_key in vr_set else 0.0

        qg_pos = None
        if isinstance(qg, dict):
            try:
                qg_pos = int(qg.get(nome_key)) if qg.get(nome_key) is not None else None
            except Exception:
                qg_pos = None

        rec5 = None
        if isinstance(rp5, dict) and isinstance(rp5.get(nome_key), list):
            lista5 = [int(x) for x in rp5.get(nome_key, []) if int(x) > 0]
            rec5 = _media_lista(lista5)

        hist = None
        if isinstance(hc, dict):
            try:
                hist_val = hc.get(nome_key)
                hist = float(hist_val) if hist_val is not None else None
            except Exception:
                hist = None

        componentes: list[tuple[float, float]] = []
        if qg_pos is not None and qg_pos > 0:
            componentes.append((0.40, float(qg_pos)))
        if rec5 is not None and rec5 > 0:
            componentes.append((0.35, rec5))
        if hist is not None and hist > 0:
            componentes.append((0.25, hist))

        if componentes:
            soma_pesos = sum(w for w, _ in componentes)
            mu = sum(w * v for w, v in componentes) / soma_pesos
        elif base_rank is not None:
            mu = float(base_rank)
        else:
            mu = float(n_pos) * 0.72

        # Ajustes finos por tendência recente e volta rápida
        mu = mu - (0.20 * float(delta)) + ajuste_vr

        # Penalidade por risco de abandono recente (DNF)
        dnf_rate = 0.0
        if isinstance(dnf, dict):
            try:
                dnf_rate = float(dnf.get(nome_key, 0.0) or 0.0)
            except Exception:
                dnf_rate = 0.0
        mu += _clamp(dnf_rate, 0.0, 0.8) * 4.0
        mu = _clamp(mu, 1.0, float(n_pos))

        # Sigma adaptativo por consistência (ultimas 8 corridas), com limites robustos
        sigma = 1.9 if not is_sprint else 1.5
        if isinstance(rp8, dict) and isinstance(rp8.get(nome_key), list):
            lista8_raw = [int(x) for x in rp8.get(nome_key, []) if int(x) > 0]
            if lista8_raw:
                lista8 = [int(_clamp(float(x), 1.0, float(max(n_pos, 20)))) for x in lista8_raw]
                std8 = _desvio_padrao_populacao(lista8)
                if std8 is not None:
                    if is_sprint:
                        sigma = _clamp(float(std8), 0.9, 3.2)
                    else:
                        sigma = _clamp(float(std8), 1.1, 4.0)

        row = []
        for pos_idx in range(1, n_pos + 1):
            z = (float(pos_idx) - mu) / sigma
            row.append(math.exp(-0.5 * z * z))
        s = sum(row)
        if s <= 0:
            row = [1.0 / n_pos] * n_pos
        else:
            row = [v / s for v in row]
        prob_por_piloto.append(row)

    # Escolhe posição única por piloto maximizando probabilidade (1 piloto por posição).
    # A pontuação estimada é calculada depois como fichas * pontos_da_posicao_escolhida.
    pilotos_top = pilotos_validos[:n_pos]
    probs_top = prob_por_piloto[:n_pos]
    m = len(pilotos_top)

    dp: dict[tuple[int, int], tuple[float, list[int]]] = {(0, 0): (0.0, [])}
    for i in range(m):
        novo_dp: dict[tuple[int, int], tuple[float, list[int]]] = {}
        for (idx, mask), (score, escolha) in dp.items():
            if idx != i:
                continue
            for pos0 in range(n_pos):
                bit = 1 << pos0
                if mask & bit:
                    continue
                p = probs_top[i][pos0]
                ganho = p
                chave = (i + 1, mask | bit)
                atual = novo_dp.get(chave)
                candidato = (score + ganho, escolha + [pos0 + 1])
                if atual is None or candidato[0] > atual[0]:
                    novo_dp[chave] = candidato
        dp = novo_dp

    melhor_score = -1.0
    melhor_escolha: list[int] = []
    for (idx, _mask), (score, escolha) in dp.items():
        if idx == m and score > melhor_score:
            melhor_score = score
            melhor_escolha = escolha

    if not melhor_escolha:
        # fallback robusto: posições em ordem de maior probabilidade sem repetir
        melhor_escolha = []
        usadas: set[int] = set()
        for row in probs_top:
            ordem = sorted(range(1, n_pos + 1), key=lambda p: row[p - 1], reverse=True)
            pos_sel = next((p for p in ordem if p not in usadas), ordem[0])
            melhor_escolha.append(pos_sel)
            usadas.add(pos_sel)

    pontos_estimados = 0.0
    detalhes_linhas: list[str] = []
    probs_escolhidas: list[tuple[float, int]] = []
    probs_media_simples: list[float] = []
    for (piloto, ficha_i), pos_sel, row in zip(pilotos_top, melhor_escolha, probs_top):
        prob_sel = max(0.001, min(0.999, float(row[pos_sel - 1])))
        nome_key = _norm_nome_piloto(piloto)
        dnf_rate = 0.0
        if isinstance(dnf, dict):
            try:
                dnf_rate = float(dnf.get(nome_key, 0.0) or 0.0)
            except Exception:
                dnf_rate = 0.0
        fator_dnf = 1.0 - _clamp(dnf_rate, 0.0, 1.0)
        pontos_estimados += float(pontos_lista[pos_sel - 1]) * float(ficha_i) * fator_dnf
        probs_escolhidas.append((prob_sel, ficha_i))
        probs_media_simples.append(prob_sel)
        detalhes_linhas.append(
            f"{piloto}: ficha={ficha_i}, pos~{pos_sel}, p={prob_sel:.3f}, dnf={dnf_rate:.2f}, fator_dnf={fator_dnf:.2f}"
        )

    bonus_11 = float(regras.get("pontos_11_colocado", 25) or 25)
    p11_key = _norm_nome_piloto(piloto_11)
    p11_pos = pos_por_nome.get(p11_key)

    freq_11 = None
    if isinstance(fr11, dict):
        try:
            val = fr11.get(p11_key)
            if val is not None:
                freq_11 = float(val)
        except Exception:
            freq_11 = None

    media_campo_11 = 0.05
    if isinstance(fr11, dict) and fr11:
        try:
            media_campo_11 = float(sum(float(v) for v in fr11.values()) / len(fr11))
        except Exception:
            media_campo_11 = 0.05

    if freq_11 is not None:
        chance_11 = _clamp(freq_11, 0.01, 0.35)
    else:
        chance_11 = media_campo_11
        if p11_pos is not None:
            if p11_pos <= 5:
                chance_11 *= 0.60
            elif 8 <= p11_pos <= 14:
                chance_11 *= 1.40
            elif p11_pos >= 15:
                chance_11 *= 1.20
        chance_11 = _clamp(chance_11, 0.01, 0.35)

    bonus_11_estimado = bonus_11 * chance_11

    # Confianca composta desacoplada dos pontos estimados.
    if pilotos_top:
        n_com_sinal = 0
        for piloto, _ in pilotos_top:
            nome_key = _norm_nome_piloto(piloto)
            tem_sinal = (
                nome_key in pos_por_nome
                or (isinstance(qg, dict) and nome_key in qg)
                or (isinstance(rp5, dict) and nome_key in rp5)
                or (isinstance(hc, dict) and nome_key in hc)
            )
            if tem_sinal:
                n_com_sinal += 1
        cob_sinal = float(n_com_sinal) / float(len(pilotos_top))
    else:
        cob_sinal = 0.0

    soma_fichas = float(sum(f for _, f in pilotos_top)) if pilotos_top else 0.0
    fichas_em_top5 = 0.0
    if soma_fichas > 0:
        for piloto, ficha_i in pilotos_top:
            nome_key = _norm_nome_piloto(piloto)
            if int(pos_por_nome.get(nome_key, 99)) <= 5:
                fichas_em_top5 += float(ficha_i)
    conc_fichas = (fichas_em_top5 / soma_fichas) if soma_fichas > 0 else 0.0

    prob_media = (sum(probs_media_simples) / len(probs_media_simples)) if probs_media_simples else 0.0
    indice = (0.35 * cob_sinal) + (0.25 * conc_fichas) + (0.40 * prob_media)
    probabilidade_combinada = int(round(_clamp(indice, 0.0, 1.0) * 100.0))

    return {
        "pontos_estimados": round(pontos_estimados, 1),
        "bonus_11_estimado": round(bonus_11_estimado, 1),
        "chance_11": int(round(chance_11 * 100)),
        "probabilidade_combinada": max(0, min(100, probabilidade_combinada)),
        "criterios": "Ergast(quali+forma+circuito+dnf+11o) + regras da prova",
        "detalhes": " | ".join(detalhes_linhas[:5]),
    }


def _gerar_copy_email_aposta(
    nome_usuario: str,
    nome_prova: str,
    pilotos: list[str],
    fichas: list[int],
    piloto_11: str,
    pontos_estimados: Optional[float],
    probabilidade: Optional[Union[int, float]],
) -> tuple[str, str]:
    """Gera abertura/fechamento mais humanos com variação determinística por aposta."""
    assinatura = (
        f"{nome_usuario}|{nome_prova}|{','.join(pilotos)}|{','.join(map(str, fichas))}|{piloto_11}|{pontos_estimados}|{probabilidade}"
    )
    seed = int(hashlib.sha256(assinatura.encode("utf-8")).hexdigest()[:8], 16)

    aberturas = [
        "Seu pitwall confirmou a estratégia e a aposta já está no grid.",
        "A equipe validou o plano: aposta registrada e pronta para luzes apagarem.",
        "Missão concluída no box: sua combinação foi salva com sucesso.",
        "Aposta travada no sistema. Agora é torcer para a leitura de corrida bater.",
        "Tudo certo por aqui: sua equipe entrou oficialmente na prova.",
    ]

    fechamentos = [
        "Que venha a corrida. Se bater, é visão estratégica; se não bater, foi apenas entretenimento de alto nível.",
        "Agora é com o cronômetro e um pouco de caos controlado de fim de semana de F1.",
        "Boa sorte no fim de semana. Planejamento você já fez; o resto é com o asfalto.",
        "Se essa leitura encaixar, tem cara de domingo feliz no bolão.",
        "Respira e confia: a estratégia já foi para pista.",
    ]

    abertura = aberturas[seed % len(aberturas)]

    fecho_base = fechamentos[(seed // 7) % len(fechamentos)]
    if probabilidade is not None:
        try:
            prob_i = int(float(probabilidade))
        except Exception:
            prob_i = None
        if prob_i is not None:
            if prob_i >= 70:
                fecho_base = "A estimativa está confiante. Se o roteiro colaborar, essa aposta pode render forte."
            elif prob_i <= 35:
                fecho_base = "A leitura indica risco alto, mas é exatamente daí que saem as histórias boas do bolão."

    return abertura, fecho_base


def _canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _build_compact_json_with_meta(payload_data: dict) -> tuple[str, str]:
    """Retorna JSON compacto e metadata do tipo de fallback aplicado."""
    compact = _canonical_json(payload_data)
    if len(compact) <= MAX_PERPLEXITY_CONTEXT_CHARS:
        return compact, "none"

    reduced = _reduce_context_for_limit(payload_data)
    compact_reduced = _canonical_json(reduced)
    if len(compact_reduced) <= MAX_PERPLEXITY_CONTEXT_CHARS:
        return compact_reduced, "reduced"

    minimal = _minimal_context_for_limit(payload_data)
    return _canonical_json(minimal), "minimal"


def _reduce_context_for_limit(data: dict) -> dict:
    """Fallback progressivo para manter contexto útil abaixo do limite de tamanho."""
    d = dict(data)

    # 1) Remove voltas rápidas (sinal útil, mas menos crítico para aposta)
    erg = dict(d.get("erg", {}))
    if "vr" in erg:
        erg = dict(erg)
        erg["vr"] = []
        d["erg"] = erg

    # 2) Enxuga histórico local e cenário
    if "ua" in d:
        d["ua"] = d.get("ua", [])[:1]
    if "cz" in d:
        d["cz"] = d.get("cz", [])[:1]

    # 3) Enxuga ainda mais Ergast
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
    """Fallback mínimo que preserva JSON válido e os campos essenciais para decisão."""
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
            "du": {
                "top": du.get("top", [])[:2],
                "bot": du.get("bot", [])[:1],
            },
            "vr": [],
        },
    }


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
        "rg": {
            "min": min_pilotos,
            "qf": qtd_fichas,
            "fmax": fichas_max,
            "me": permite_mesma_equipe,
        },
        "ua": ultimas_apostas,
        "cz": cenario,
        "erg": contexto_ergast,
    }

    return _build_compact_json_with_meta(payload_data)


def _validar_formato_json_resposta(parsed: dict) -> bool:
    """Valida formato exigido: {"pilotos": [...], "fichas": [...], "piloto_11": "..."}."""
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

    api_key = ""
    model = "sonar"
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    model = os.environ.get("PERPLEXITY_MODEL", "sonar")
    if not api_key:
        return None

    pilotos_disponiveis: list[str] = [str(x) for x in pilotos_df['nome'].tolist()] if not pilotos_df.empty else []
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

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
        pilotos = [str(p).strip() for p in parsed.get('pilotos', []) if str(p).strip()]
        fichas = [int(x) for x in parsed.get('fichas', [])]
        piloto_11 = str(parsed.get('piloto_11', '')).strip()
        if not pilotos or not fichas or not piloto_11:
            return None
        return pilotos, fichas, piloto_11
    except Exception as e:
        logger.warning(f"Falha na geração via Perplexity para aposta estratégica: {e}")
        return None

def _parse_datetime_sp(date_str: str, time_str: str):
    """Tenta parsear data e hora com ou sem segundos e retorna timezone America/Sao_Paulo."""
    return parse_datetime_sao_paulo(date_str, time_str)

def pode_fazer_aposta(data_prova_str, horario_prova_str, horario_usuario=None):
    """
    Verifica se o usuário pode fazer aposta comparando horário local com horário de São Paulo.
    """
    try:
        horario_limite_sp = _parse_datetime_sp(data_prova_str, horario_prova_str)

        if horario_usuario is None:
            horario_usuario = now_sao_paulo()
        elif not horario_usuario.tzinfo:
            horario_usuario = horario_usuario.replace(tzinfo=SAO_PAULO_TZ)

        horario_usuario_utc = horario_usuario.astimezone(ZoneInfo("UTC"))
        horario_limite_utc = horario_limite_sp.astimezone(ZoneInfo("UTC"))

        pode = horario_usuario_utc <= horario_limite_utc
        mensagem = f"Aposta {'permitida' if pode else 'bloqueada'} (Horário limite SP: {horario_limite_sp.strftime('%d/%m/%Y %H:%M:%S')})"

        return pode, mensagem, horario_limite_sp
    except Exception as e:
        return False, f"Erro ao validar horário: {str(e)}", None

def salvar_aposta(
    usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova,
    automatica=0, horario_forcado=None, temporada: Optional[str] = None, show_errors=True,
    permitir_salvar_tardia: bool = False,
    error_reporter: Optional[Callable[[str], None]] = None,
):
    def _report_error(message: str) -> None:
        if show_errors and error_reporter is not None:
            error_reporter(message)

    try:
        payload = BetSubmissionInput(
            usuario_id=usuario_id,
            prova_id=prova_id,
            pilotos=pilotos,
            fichas=fichas,
            piloto_11=piloto_11,
            nome_prova=nome_prova,
            automatica=automatica,
            temporada=temporada,
        )
        usuario_id = payload.usuario_id
        prova_id = payload.prova_id
        pilotos = payload.pilotos
        fichas = payload.fichas
        piloto_11 = payload.piloto_11
        nome_prova = payload.nome_prova
        automatica = payload.automatica
        temporada = payload.temporada
    except ValidationError as exc:
        _report_error("Dados inválidos para registrar aposta.")
        logger.warning("Aposta rejeitada por validacao: %s", exc.errors())
        return False

    nome_prova_bd, data_prova, horario_prova = get_horario_prova(prova_id)
    if not horario_prova or not nome_prova_bd or not data_prova:
        _report_error("Prova não encontrada ou horário/nome/data não cadastrados.")
        return False

    # Determinar tipo da prova usando coluna `tipo` quando disponível; fallback por nome
    try:
        prov_df = get_provas_df(temporada)
        tipo_col = None
        if not prov_df.empty:
            row = prov_df[prov_df['id'] == prova_id]
            if not row.empty and 'tipo' in row.columns and pd.notna(row.iloc[0]['tipo']):
                tipo_col = str(row.iloc[0]['tipo']).strip()
        tipo_prova_regra = 'Sprint' if (tipo_col and tipo_col.lower() == 'sprint') or ('sprint' in str(nome_prova_bd).lower()) else 'Normal'
    except Exception:
        tipo_prova_regra = 'Sprint' if 'sprint' in str(nome_prova_bd).lower() else 'Normal'
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova_regra)
    
    quantidade_fichas = regras.get('quantidade_fichas', 15)
    min_pilotos = regras.get('min_pilotos', 3)
    max_por_piloto = int(regras.get('fichas_por_piloto', quantidade_fichas))

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < min_pilotos or sum(fichas) != quantidade_fichas or (fichas and max(fichas) > max_por_piloto):
        msg = f"Regra exige: mín {min_pilotos} pilotos, total {quantidade_fichas} fichas, máx {max_por_piloto} por piloto."
        _report_error(f"Dados inválidos para aposta. {msg}")
        return False

    horario_limite = _parse_datetime_sp(data_prova, horario_prova)

    agora_sp = horario_forcado or now_sao_paulo()
    tipo_aposta = 0 if agora_sp <= horario_limite else 1

    dados_pilotos = ', '.join(pilotos)
    dados_fichas = ', '.join(map(str, fichas))
    ip_apostador = get_client_ip()

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        _report_error(f"Usuário não encontrado: id={usuario_id}")
        return False
    status_usuario = str(usuario.get('status', '')).strip().lower()
    if status_usuario and status_usuario != 'ativo':
        _report_error("Usuário inativo não pode efetuar apostas.")
        return False

    try:
        with db_connect() as conn:
            c = conn.cursor()
            aposta_cols = get_table_columns(conn, 'apostas')

            if temporada is None:
                temporada = str(datetime.now().year)

            if tipo_aposta == 0 or permitir_salvar_tardia:
                if 'temporada' in aposta_cols:
                    c.execute('DELETE FROM apostas WHERE usuario_id=%s AND prova_id=%s AND temporada=%s', (usuario_id, prova_id, temporada))
                else:
                    c.execute('DELETE FROM apostas WHERE usuario_id=%s AND prova_id=%s', (usuario_id, prova_id))

                data_envio = agora_sp.isoformat()
                if 'temporada' in aposta_cols:
                    c.execute(
                        '''
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica, temporada)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''',
                        (
                            usuario_id, prova_id, data_envio, ','.join(pilotos), ','.join(map(str, fichas)),
                            piloto_11, nome_prova_bd, automatica, temporada
                        )
                    )
                else:
                    c.execute(
                        '''
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''',
                        (
                            usuario_id, prova_id, data_envio, ','.join(pilotos), ','.join(map(str, fichas)),
                            piloto_11, nome_prova_bd, automatica
                        )
                    )
            else:
                # Aposta tardia não salva quando não permitido
                _report_error("Aposta fora do horário limite.")
                try:
                    tentativa_str = agora_sp.strftime('%d/%m/%Y %H:%M:%S')
                    limite_str = horario_limite.strftime('%d/%m/%Y %H:%M:%S')
                    corpo_email = (
                        f"<p>Olá {html.escape(usuario['nome'])},</p>"
                        f"<p>Sua aposta para a prova <b>{html.escape(nome_prova_bd)}</b> não foi efetivada.</p>"
                        "<p><b>Motivo:</b> prazo encerrado (aposta fora do horário limite).</p>"
                        f"<p><b>Horário limite:</b> {limite_str} (America/Sao_Paulo)</p>"
                        f"<p><b>Horário da tentativa:</b> {tentativa_str} (America/Sao_Paulo)</p>"
                        "<p>Se precisar de ajuda, fale com a administração.</p>"
                    )
                    enviar_email(usuario['email'], f"Aposta não efetivada - {nome_prova_bd}", corpo_email)
                except Exception as e:
                    logger.warning(
                        "Falha ao enviar email de aposta rejeitada para %s: %s",
                        redact_identifier(str(usuario.get('email', ''))),
                        e,
                    )
                try:
                    registrar_log_aposta(
                        usuario_id=usuario_id,
                        prova_id=prova_id,
                        apostador=usuario['nome'],
                        pilotos=dados_pilotos,
                        aposta=dados_fichas,
                        nome_prova=nome_prova_bd,
                        piloto_11=piloto_11,
                        tipo_aposta=tipo_aposta,
                        automatica=automatica,
                        horario=agora_sp,
                        ip_address=ip_apostador,
                        temporada=temporada,
                        status='Rejeitada'
                    )
                except Exception as e:
                    logger.warning(
                        "Falha ao registrar log de aposta rejeitada para %s: %s",
                        redact_identifier(str(usuario.get('email', ''))),
                        e,
                    )
                return False
            conn.commit()

            corpo_email = (
                f"<p>Olá {html.escape(usuario['nome'])},</p>"
                f"<p>Sua aposta para a prova <b>{html.escape(nome_prova_bd)}</b> foi registrada com sucesso.</p>"
                "<p><b>Detalhes:</b></p>"
                "<ul>"
                f"<li>Pilotos: {html.escape(', '.join(pilotos))}</li>"
                f"<li>Fichas: {html.escape(', '.join(map(str, fichas)))}</li>"
                f"<li>Palpite para 11º colocado: {html.escape(piloto_11)}</li>"
                "</ul>"
                "<p>Boa sorte na prova!</p>"
            )

            try:
                contexto_ergast_email = _get_contexto_temporada_atual_ergast(
                    temporada=str(temporada or datetime.now().year),
                    nome_prova=nome_prova_bd,
                )
                estimativa_email = _estimar_pontos_aposta_ergast(
                    pilotos=pilotos,
                    fichas=fichas,
                    piloto_11=piloto_11,
                    tipo_prova=tipo_prova_regra,
                    regras=regras,
                    contexto_ergast=contexto_ergast_email,
                )
                pontos_estimados = estimativa_email.get("pontos_estimados")
                bonus_11_estimado = estimativa_email.get("bonus_11_estimado")
                chance_11 = estimativa_email.get("chance_11")
                probabilidade_combinada = estimativa_email.get("probabilidade_combinada")
                criterios_estimativa = str(estimativa_email.get("criterios", "Ergast + regras da prova"))
                detalhes_estimativa = str(estimativa_email.get("detalhes", "")).strip()

                analise = gerar_analise_aposta_com_probabilidade(
                    nome_usuario=usuario.get('nome', ''),
                    contexto_aposta=f"Prova {nome_prova_bd}",
                    detalhes_aposta=(
                        f"Pilotos: {', '.join(pilotos)}; "
                        f"Fichas: {', '.join(map(str, fichas))}; "
                        f"11º: {piloto_11}; "
                        f"Estimativa de pontos (Ergast): {pontos_estimados}; "
                        f"Bônus 11º esperado: {bonus_11_estimado} ({chance_11}%); "
                        f"Critérios: {criterios_estimativa}; "
                        f"Sinais: {detalhes_estimativa}"
                    ),
                )
                comentario = str(analise.get("comentario", "")).strip()
                probabilidade = analise.get("probabilidade")
                resumo = str(analise.get("resumo", "")).strip()

                # Probabilidade principal do email deve seguir a combinação das probabilidades por piloto.
                if probabilidade_combinada is not None:
                    probabilidade = probabilidade_combinada

                # Mantém coerência entre chance de acerto e pontos projetados.
                try:
                    prob_i = int(float(probabilidade)) if probabilidade is not None else None
                except Exception:
                    prob_i = None
                try:
                    pontos_i = float(pontos_estimados) if pontos_estimados is not None else None
                except Exception:
                    pontos_i = None
                if pontos_i is not None:
                    cap_por_pontos = int(max(10, min(95, round(pontos_i * 1.6))))
                    if prob_i is None:
                        prob_i = cap_por_pontos
                    else:
                        prob_i = min(prob_i, cap_por_pontos)
                if prob_i is not None:
                    probabilidade = max(0, min(100, prob_i))

                abertura_email, fechamento_email = _gerar_copy_email_aposta(
                    nome_usuario=str(usuario.get('nome', 'Participante')),
                    nome_prova=nome_prova_bd,
                    pilotos=pilotos,
                    fichas=fichas,
                    piloto_11=piloto_11,
                    pontos_estimados=(float(pontos_estimados) if pontos_estimados is not None else None),
                    probabilidade=probabilidade,
                )

                previsao_html = ""
                if comentario:
                    previsao_html += "<p>" + "<br>".join(html.escape(comentario).splitlines()) + "</p>"
                if pontos_estimados is not None:
                    previsao_html += (
                        f"<p><b>Estimativa de pontos:</b> {float(pontos_estimados):.1f}</p>"
                    )
                if chance_11 is not None:
                    previsao_html += f"<p><b>Probabilidade de acerto do 11º colocado:</b> {int(chance_11)}%</p>"
                if probabilidade is not None:
                    previsao_html += f"<p><b>Probabilidade estimada de acerto:</b> {int(probabilidade)}%</p>"

                corpo_email = (
                    f"<p>Olá {html.escape(usuario['nome'])},</p>"
                    f"<p>Sua aposta para a prova <b>{html.escape(nome_prova_bd)}</b> foi registrada com sucesso.</p>"
                    f"<p>{html.escape(abertura_email)}</p>"
                    "<p><b>Detalhes:</b></p>"
                    "<ul>"
                    f"<li>Pilotos: {html.escape(', '.join(pilotos))}</li>"
                    f"<li>Fichas: {html.escape(', '.join(map(str, fichas)))}</li>"
                    f"<li>Palpite para 11º colocado: {html.escape(piloto_11)}</li>"
                    "</ul>"
                    f"{previsao_html}"
                    f"<p>{html.escape(fechamento_email)}</p>"
                    "<p><small><b>Aviso de estimativa:</b> a probabilidade informada é apenas uma projeção estatística/opinativa com base em informações disponíveis e pode variar a qualquer momento. Não constitui garantia de resultado esportivo nem direito a pontuação, prevalecendo sempre as regras oficiais do bolão.</small></p>"
                )
            except Exception as e:
                logger.exception(
                    "Falha ao montar conteúdo avançado do email de aposta para %s: %s",
                    redact_identifier(str(usuario.get('email', ''))),
                    e,
                )

            try:
                email_ok = enviar_email(usuario['email'], f"Aposta registrada - {nome_prova_bd}", corpo_email)
                if not email_ok:
                    logger.warning(
                        "Falha de envio de email de aposta para %s (prova_id=%s)",
                        redact_identifier(str(usuario.get('email', ''))),
                        prova_id,
                    )
            except Exception as e:
                logger.warning(
                    "Falha ao enviar email de aposta para %s: %s",
                    redact_identifier(str(usuario.get('email', ''))),
                    e,
                )

    except Exception as e:
        _report_error("Erro ao salvar aposta.")
        logger.exception("Erro ao salvar aposta: %s", e)
        return False

    registrar_log_aposta(
        usuario_id=usuario_id,
        prova_id=prova_id,
        apostador=usuario['nome'],
        pilotos=dados_pilotos,
        aposta=dados_fichas,
        nome_prova=nome_prova_bd,
        piloto_11=piloto_11,
        tipo_aposta=tipo_aposta,
        automatica=automatica,
        horario=agora_sp,
        ip_address=ip_apostador,
        temporada=temporada,
        status='Registrada'
    )
    return True

def gerar_aposta_aleatoria(pilotos_df):
    import random
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df['status'] == 'Ativo'])
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    if len(equipes_unicas) < 3 or pilotos_df.empty:
        return [], [], None
    
    equipes_selecionadas = random.sample(equipes_unicas, min(5, len(equipes_unicas)))
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
        if pilotos_equipe:
            pilotos_sel.append(random.choice(pilotos_equipe))
    
    # Validar se conseguimos selecionar piloto suficientes
    if len(pilotos_sel) < 3:
        return [], [], None
    
    # Gerar fichas que totalizam exatamente 15
    num_pilotos = len(pilotos_sel)
    fichas = [1] * num_pilotos  # Cada piloto começa com 1 ficha
    fichas_restantes = 15 - num_pilotos  # Fichas a distribuir
    
    # Distribuir fichas restantes aleatoriamente
    for _ in range(fichas_restantes):
        idx = random.randint(0, num_pilotos - 1)
        fichas[idx] += 1
        
    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)
    
    return pilotos_sel, fichas, piloto_11

def gerar_aposta_aleatoria_com_regras(pilotos_df, regras: dict):
    """Gera aposta aleatória respeitando as regras (total de fichas, mínimo de pilotos, limite por piloto).
    Considera possibilidade de mesma equipe quando necessário para atingir o número de pilotos requerido.
    """
    import random
    import math
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df['status'] == 'Ativo'])
    if pilotos_df.empty:
        return [], [], None
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

    # Quantidade mínima de pilotos para suportar o limite por piloto
    pilotos_necessarios_por_cap = max(1, math.ceil(qtd_fichas / max(1, fichas_max)))
    alvo_pilotos = max(min_pilotos, pilotos_necessarios_por_cap)

    pilotos_sel = []
    if len(equipes_unicas) >= alvo_pilotos:
        # Escolhe equipes diferentes
        equipes_selecionadas = random.sample(equipes_unicas, alvo_pilotos)
        for equipe in equipes_selecionadas:
            pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
    else:
        # Não há equipes suficientes; se permitido, escolhe pilotos adicionais de equipes repetidas
        if not permite_mesma_equipe:
            return [], [], None
        # Primeiro pega um de cada equipe
        for equipe in equipes_unicas:
            pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
        # Completa com pilotos aleatórios (permitindo 2 da mesma equipe)
        todos_pilotos = pilotos_df['nome'].tolist()
        safety = 10000
        while len(pilotos_sel) < alvo_pilotos and safety > 0:
            safety -= 1
            candidato = random.choice(todos_pilotos)
            if candidato not in pilotos_sel:
                pilotos_sel.append(candidato)
        if len(pilotos_sel) < alvo_pilotos:
            return [], [], None

    # Distribuição de fichas obedecendo limite por piloto
    num_pilotos = len(pilotos_sel)
    fichas = [1] * num_pilotos
    fichas_restantes = qtd_fichas - num_pilotos
    if fichas_restantes < 0:
        return [], [], None
    safety = 10000
    while fichas_restantes > 0 and safety > 0:
        safety -= 1
        idx = random.randint(0, num_pilotos - 1)
        if fichas[idx] < fichas_max:
            fichas[idx] += 1
            fichas_restantes -= 1
    if fichas_restantes > 0:
        return [], [], None

    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)

    return pilotos_sel, fichas, piloto_11

def ajustar_aposta_para_regras(pilotos: list[str], fichas: list[int], regras: dict, pilotos_df: pd.DataFrame):
    """Ajusta uma aposta existente (copiada) para obedecer regras da temporada.
    - Garante soma de fichas conforme regra
    - Respeita limite por piloto
    - Garante mínimo de pilotos (adicionando pilotos se necessário)
    Retorna (pilotos_ajustados, fichas_ajustadas) ou ([], []) se não for possível.
    """
    import math, random
    if not pilotos:
        return [], []
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))

    # Normalizar tamanhos
    n = min(len(pilotos), len(fichas))
    pilotos = [p.strip() for p in pilotos[:n]]
    fichas = [int(x) for x in fichas[:n]]
    # Trocar zeros negativos por zero e tratar negativos
    fichas = [max(0, x) for x in fichas]

    # Garante mínimo de pilotos
    if len(pilotos) < min_pilotos:
        todos_pilotos = pilotos_df['nome'].tolist()
        candidatos = [p for p in todos_pilotos if p not in set(pilotos)]
        safety = 10000
        while len(pilotos) < min_pilotos and candidatos and safety > 0:
            safety -= 1
            novo = random.choice(candidatos)
            candidatos.remove(novo)
            pilotos.append(novo)
            fichas.append(0)
        if len(pilotos) < min_pilotos:
            return [], []

    # Impõe limite por piloto
    fichas = [min(x, fichas_max) for x in fichas]

    soma = sum(fichas)
    # Ajusta soma para o exigido
    if soma > qtd_fichas:
        # Reduz das maiores entradas primeiro
        for _ in range(soma - qtd_fichas):
            idx_max = max(range(len(fichas)), key=lambda i: fichas[i])
            if fichas[idx_max] > 0:
                fichas[idx_max] -= 1
    elif soma < qtd_fichas:
        # Aumenta respeitando limite por piloto
        faltam = qtd_fichas - soma
        safety = 100000
        while faltam > 0 and safety > 0:
            safety -= 1
            idx = random.randint(0, len(fichas) - 1)
            if fichas[idx] < fichas_max:
                fichas[idx] += 1
                faltam -= 1
            # Se ficar travado por limite, tenta expandir pilotos
            if safety % 1000 == 0 and faltam > 0:
                todos_pilotos = pilotos_df['nome'].tolist()
                candidatos = [p for p in todos_pilotos if p not in set(pilotos)]
                if candidatos:
                    novo = random.choice(candidatos)
                    pilotos.append(novo)
                    fichas.append(0)
    # Validação final
    if sum(fichas) != qtd_fichas or len(pilotos) < min_pilotos:
        return [], []
    return pilotos, fichas

def _determinar_tipo_prova(prova_row: Union[pd.Series, dict], nome_prova: Optional[str]) -> str:
    try:
        if isinstance(prova_row, dict):
            t = prova_row.get('tipo')
        else:
            t = prova_row['tipo'] if 'tipo' in prova_row and pd.notna(prova_row['tipo']) else None
    except Exception:
        t = None
    if t and str(t).strip().lower() == 'sprint':
        return 'Sprint'
    if nome_prova and 'sprint' in str(nome_prova).lower():
        return 'Sprint'
    return 'Normal'

def gerar_aposta_automatica(usuario_id, prova_id, nome_prova, apostas_df, provas_df, temporada=None):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"
        
    prova_atual = provas_df[provas_df['id'] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."
        
    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)
    
    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id) & 
        (apostas_df["prova_id"] == prova_id) & 
        ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."
        
    ap_ant = pd.DataFrame()
    prova_id_min = None
    try:
        prova_id_min = int(provas_df['id'].min()) if not provas_df.empty else None
    except Exception:
        prova_id_min = None

    # Encontrar a prova anterior pela data/horario (na mesma temporada)
    try:
        provas_tmp = provas_df.copy()
        if 'data' in provas_tmp.columns:
            provas_tmp['__data_dt'] = pd.to_datetime(provas_tmp['data'], errors='coerce')
        else:
            provas_tmp['__data_dt'] = pd.NaT
        provas_tmp['__hora_str'] = provas_tmp.get('horario_prova', '00:00:00')
        provas_tmp['__hora_dt'] = pd.to_datetime(provas_tmp['__hora_str'], format='%H:%M:%S', errors='coerce')
        provas_tmp['__hora_dt'] = provas_tmp['__hora_dt'].fillna(
            pd.to_datetime('00:00:00', format='%H:%M:%S')
        )
        provas_tmp['__prova_dt'] = provas_tmp['__data_dt'] + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.hour, unit='h'
        ) + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.minute, unit='m'
        ) + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.second, unit='s'
        )
        provas_tmp = provas_tmp.sort_values(['__prova_dt', 'id'])

        prova_atual_row = provas_tmp[provas_tmp['id'] == prova_id]
        if not prova_atual_row.empty:
            prova_atual_dt = prova_atual_row.iloc[0]['__prova_dt']
            provas_anteriores = provas_tmp[provas_tmp['__prova_dt'] < prova_atual_dt]
            if not provas_anteriores.empty:
                prova_ant_id = int(provas_anteriores.iloc[-1]['id'])
                ap_ant = apostas_df[
                    (apostas_df['usuario_id'] == usuario_id) &
                    (apostas_df['prova_id'] == prova_ant_id)
                ]
    except Exception:
        ap_ant = pd.DataFrame()

    if ap_ant.empty:
        try:
            provas_sorted = provas_df.sort_values('id')
            prev_rows = provas_sorted[provas_sorted['id'] < prova_id]
            if not prev_rows.empty:
                prova_ant_id = int(prev_rows.iloc[-1]['id'])
                ap_ant = apostas_df[
                    (apostas_df['usuario_id'] == usuario_id) &
                    (apostas_df['prova_id'] == prova_ant_id)
                ]
        except Exception:
            ap_ant = pd.DataFrame()
    
    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df['status'] == 'Ativo'])

    if not ap_ant.empty:
        ap_ant = ap_ant.iloc[0]
        pilotos_ant = [p.strip() for p in ap_ant['pilotos'].split(",")]
        fichas_ant = list(map(int, ap_ant['fichas'].split(",")))
        piloto_11_ant = ap_ant['piloto_11'].strip()
        # Ajustar aposta copiada para obedecer regras da prova atual (ex.: Sprint x Normal)
        pilotos_aj, fichas_aj = ajustar_aposta_para_regras(pilotos_ant, fichas_ant, regras, pilotos_df)
        if not pilotos_aj:
            # Se não conseguir ajustar, gera aleatória com regras
            pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        else:
            pilotos_ant, fichas_ant = pilotos_aj, fichas_aj
    else:
        # Gerar aleatoria apenas na primeira prova do campeonato
        if prova_id_min is not None and prova_id != prova_id_min:
            return False, "Sem aposta anterior para copiar. Gere apenas na primeira prova."
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        
    if not pilotos_ant:
        return False, "Não há dados válidos para gerar aposta automática."
        
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(automatica) AS max_auto FROM apostas WHERE usuario_id=%s', (usuario_id,))
        max_auto = c.fetchone()['max_auto'] or 0
        nova_auto = 1 if max_auto is None else max_auto + 1
        
    sucesso = salvar_aposta(
        usuario_id, prova_id, pilotos_ant, fichas_ant, piloto_11_ant, nome_prova,
        automatica=nova_auto, temporada=temporada, show_errors=False,
        permitir_salvar_tardia=True
    )
    
    return (True, "Aposta automática gerada!") if sucesso else (False, "Falha ao salvar.")


def gerar_aposta_sem_ideias(usuario_id, prova_id, nome_prova, temporada=None):
    """Gera e efetiva aposta para o participante dentro do prazo, com tentativa estratégica via Perplexity e fallback aleatório seguro."""
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"

    provas_df = get_provas_df(temporada)
    prova_atual = provas_df[provas_df['id'] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."

    data_prova = str(prova_atual['data'].iloc[0])
    horario_prova = str(prova_atual['horario_prova'].iloc[0])
    pode, msg, _ = pode_fazer_aposta(data_prova, horario_prova)
    if not pode:
        return False, f"Aposta fora do prazo. {msg}"

    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)

    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df['status'] == 'Ativo'])
    if pilotos_df.empty:
        return False, "Não há pilotos ativos para gerar aposta."

    apostas_df = get_apostas_df(temporada)
    resultados_df = get_resultados_df(temporada)
    ultimas_apostas = _get_resumo_ultimas_apostas(usuario_id, apostas_df, limite=2)
    cenario = _get_resumo_cenario_campeonato(resultados_df, provas_df, limite=2)
    contexto_ergast = _get_contexto_temporada_atual_ergast(
        temporada=str(temporada or datetime.now().year),
        nome_prova=nome_prova,
    )

    origem = "aleatória"
    sugestao = _gerar_aposta_perplexity(
        pilotos_df,
        regras,
        nome_prova,
        tipo_prova,
        ultimas_apostas,
        cenario,
        contexto_ergast,
    )
    if sugestao:
        pilotos_sel, fichas_sel, piloto_11_sel = sugestao
        if _aposta_valida_regras(pilotos_sel, fichas_sel, piloto_11_sel, pilotos_df, regras):
            origem = "estratégica"
        else:
            sugestao = None

    if not sugestao:
        pilotos_sel, fichas_sel, piloto_11_sel = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        if not pilotos_sel:
            return False, "Não foi possível gerar aposta viável com as regras atuais."

    ok = salvar_aposta(
        usuario_id=usuario_id,
        prova_id=prova_id,
        pilotos=pilotos_sel,
        fichas=fichas_sel,
        piloto_11=piloto_11_sel,
        nome_prova=nome_prova,
        automatica=0,
        temporada=temporada,
        show_errors=False,
        permitir_salvar_tardia=False,
    )

    if not ok:
        return False, "Falha ao salvar aposta gerada."

    if origem == "estratégica":
        return True, "Aposta 'Sem ideias' gerada com estratégia assistida e registrada!"
    return True, "Aposta 'Sem ideias' aleatória (fallback) registrada com sucesso!"

def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação usando:
    - Tabelas de pontos da REGRA (Normal/Sprint), com fallback FIA hardcoded
    - Fichas DINÂMICAS da aposta do usuário
    - Bônus 11º DINÂMICO da regra da temporada
    - Penalidades DINÂMICAS das regras
    
    Fórmula: Pontos = (Pontos_Regra x Fichas) + Bônus_11º - Penalidades
    """
    import ast
    
    # Tabelas de pontos FIXAS da FIA
    PONTOS_F1_NORMAL = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    PONTOS_SPRINT = [8, 7, 6, 5, 4, 3, 2, 1]
    
    ress_map = {}
    abandonos_map = {}
    for _, r in res_df.iterrows():
        try:
            ress_map[r['prova_id']] = ast.literal_eval(r['posicoes'])
        except Exception:
            continue
        # Ler lista de abandonos (comma-separated), se disponível
        try:
            if 'abandono_pilotos' in res_df.columns:
                raw = r.get('abandono_pilotos', '')
                if raw is None:
                    raw = ''
                # Normaliza string -> lista de nomes limpos
                aband_list = [p.strip() for p in str(raw).split(',') if p and p.strip()]
                abandonos_map[r['prova_id']] = set(aband_list)
            else:
                abandonos_map[r['prova_id']] = set()
        except Exception:
            abandonos_map[r['prova_id']] = set()
    
    # Mapear tipo de prova com fallback pelo nome (contém "Sprint")
    tipos = []
    if 'tipo' in prov_df.columns:
        tipos = prov_df['tipo'].fillna('').astype(str).tolist()
    else:
        tipos = [''] * len(prov_df)
    nomes = prov_df['nome'].fillna('').astype(str).tolist() if 'nome' in prov_df.columns else [''] * len(prov_df)
    tipos_resolvidos = []
    for i in range(len(prov_df)):
        t = tipos[i].strip().lower()
        n = nomes[i].strip().lower()
        if t == 'sprint' or ('sprint' in n):
            tipos_resolvidos.append('Sprint')
        else:
            tipos_resolvidos.append('Normal')
    tipos_prova = dict(zip(prov_df['id'], tipos_resolvidos))
    temporadas_prova = dict(zip(prov_df['id'], prov_df['temporada'] if 'temporada' in prov_df.columns else [str(datetime.now().year)]*len(prov_df)))
    has_temp_aposta = 'temporada' in ap_df.columns
    
    pontos = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta['prova_id']
        
        if prova_id not in ress_map:
            pontos.append(None)
            continue
        
        res = ress_map[prova_id]
        tipo = tipos_prova.get(prova_id, 'Normal')
        temporada_aposta = None
        if has_temp_aposta:
            try:
                temporada_aposta = aposta.get('temporada', None)
            except Exception:
                temporada_aposta = None
        if temporada_aposta is not None and str(temporada_aposta).strip() != "" and not pd.isna(temporada_aposta):
            temporada_prova = str(temporada_aposta)
        else:
            temporada_prova = temporadas_prova.get(prova_id, str(datetime.now().year))
        
        # Busca REGRAS DINÂMICAS da temporada (não altera pontos FIA)
        regras = get_regras_aplicaveis(temporada_prova, tipo)
        
        # Seleciona tabela de pontos da REGRA.
        # Corridas Sprint sempre usam a tabela de sprint; regra_sprint só afeta fichas/minimo, não a tabela.
        if tipo == 'Sprint':
            pontos_tabela = regras.get('pontos_sprint_posicoes') or regras.get('pontos_posicoes') or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_SPRINT
        else:
            pontos_tabela = regras.get('pontos_posicoes') or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_F1_NORMAL
        n_posicoes = len(pontos_tabela)
        
        # Bônus 11º DINÂMICO da regra
        bonus_11 = regras.get('pontos_11_colocado', 25)
        
        # Dados da aposta (fichas são DINÂMICAS - definidas pelo usuário)
        pilotos = [p.strip() for p in aposta['pilotos'].split(",")]
        fichas = list(map(int, aposta['fichas'].split(",")))  # DINÂMICO
        piloto_11 = aposta['piloto_11']
        automatica = int(aposta.get('automatica', 0))
        
        piloto_para_pos = {str(v).strip(): int(k) for k, v in res.items()}
        
        # Cálculo base: Pontos da Regra x Fichas (dinâmico)
        # Observação: multiplicador de sprint será aplicado APÓS bônus e penalidades
        pt = 0
        for i in range(len(pilotos)):
            piloto = pilotos[i]
            ficha = fichas[i] if i < len(fichas) else 0
            pos_real = piloto_para_pos.get(piloto, None)
            
            if pos_real is not None and 1 <= pos_real <= n_posicoes:
                base = pontos_tabela[pos_real - 1]
                pt += ficha * base
        
        # Bônus 11º colocado (DINÂMICO da regra)
        piloto_11_real = res.get(11, "")
        if piloto_11 == piloto_11_real:
            pt += bonus_11
        
        # Penalidade por abandono (DINÂMICA da regra):
        # Deduz `pontos_penalidade` por cada piloto apostado que esteja na lista de abandonos
        if regras.get('penalidade_abandono'):
            aband_prova = abandonos_map.get(prova_id, set())
            if aband_prova:
                # Conta apenas abandonos dentre os pilotos apostados (exclui palpite do 11º)
                num_aband_apostados = sum(1 for p in pilotos if p in aband_prova)
                deduz = regras.get('pontos_penalidade', 0) * num_aband_apostados
                if deduz:
                    pt -= deduz

        # Aplicar multiplicador de sprint APÓS bônus e penalidades
        if tipo == 'Sprint' and regras.get('pontos_dobrada'):
            pt = pt * 2

        # Penalidade apostas automáticas consecutivas (DINÂMICA)
        if automatica >= 2:
            penalidade_auto_percent = regras.get('penalidade_auto_percent', 20)
            fator = max(0, 1 - (float(penalidade_auto_percent) / 100))
            pt = round(pt * fator, 2)
        
        pontos.append(pt)
    
    return pontos

def salvar_classificacao_prova(p_id, df_c, temp=None):
    if temp is None:
        temp = str(datetime.now().year)
    
    with db_connect() as conn:
        c = conn.cursor()
        cols = get_table_columns(conn, 'posicoes_participantes')
        has_temporada = 'temporada' in cols
        
        # Safeguard: limpar entradas existentes para esta prova e temporada
        if has_temporada:
            c.execute('DELETE FROM posicoes_participantes WHERE prova_id=%s AND temporada=%s', (p_id, temp))
        else:
            c.execute('DELETE FROM posicoes_participantes WHERE prova_id=%s', (p_id,))
        
        for _, r in df_c.iterrows():
            if has_temporada:
                c.execute(
                    'INSERT INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos, temporada) VALUES (%s,%s,%s,%s,%s)',
                    (p_id, int(r['usuario_id']), int(r['posicao']), float(r['pontos']), temp)
                )
            else:
                c.execute(
                    'INSERT INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos) VALUES (%s,%s,%s,%s)',
                    (p_id, int(r['usuario_id']), int(r['posicao']), float(r['pontos']))
                )
        conn.commit()

def atualizar_classificacoes_todas_as_provas(temporada: Optional[str] = None):
    with db_connect() as conn:
        usrs = cast(
            pd.DataFrame,
            pd.read_sql(
                """
                SELECT id
                FROM usuarios
                WHERE lower(trim(coalesce(status, ''))) = 'ativo'
                """,
                conn,
            ),
        )
        provs = cast(pd.DataFrame, pd.read_sql('SELECT id, nome, data, tipo, temporada FROM provas', conn))
        apts = cast(pd.DataFrame, pd.read_sql('SELECT usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, automatica, temporada FROM apostas', conn))
        ress = cast(pd.DataFrame, pd.read_sql('SELECT prova_id, posicoes, abandono_pilotos FROM resultados', conn))
        
        import ast
        # Se temporada for fornecida, processa apenas provas dessa temporada
        if temporada and 'temporada' in provs.columns:
            provs = provs[provs['temporada'] == temporada]

        # Identificar primeira prova por temporada (quando disponível)
        primeira_prova_por_temp = {}
        if not provs.empty:
            if 'temporada' in provs.columns and 'data' in provs.columns:
                provs_dt = provs.copy()
                provs_dt['__data_dt'] = pd.to_datetime(provs_dt['data'], errors='coerce')
                for temp_val, grp in provs_dt.groupby('temporada'):
                    grp = cast(pd.DataFrame, grp)
                    grp = grp.sort_values(by=['__data_dt'])
                    if not grp.empty:
                        primeira_prova_por_temp[str(temp_val)] = int(grp.iloc[0]['id'])
            elif 'data' in provs.columns:
                provs_dt = cast(pd.DataFrame, provs.copy())
                provs_dt['__data_dt'] = pd.to_datetime(provs_dt['data'], errors='coerce')
                provs_dt = provs_dt.sort_values(by=['__data_dt'])
                if not provs_dt.empty:
                    primeira_prova_por_temp[str(datetime.now().year)] = int(provs_dt.iloc[0]['id'])
            elif not provs.empty:
                primeira_prova_por_temp[str(datetime.now().year)] = int(provs.iloc[0]['id'])
        
        for _, pr in provs.iterrows():
            pid = pr['id']
            if pid not in ress['prova_id'].values:
                continue
            
            temporada_prova = pr.get('temporada', str(datetime.now().year))
            aps = apts[apts['prova_id'] == pid]
            # Filtra apostas pela temporada se a coluna existir
            if 'temporada' in aps.columns:
                aps = aps[(aps['temporada'] == temporada_prova) | (aps['temporada'].isna())]
            if aps.empty:
                continue
                
            res_row = ress[ress['prova_id'] == pid].iloc[0]
            res_p = ast.literal_eval(res_row['posicoes'])
            piloto_11_real = res_p.get(11, "")
            
            tab = []
            first_no_base_flags = {}
            for _, u in usrs.iterrows():
                ap = aps[aps['usuario_id'] == u['id']]
                
                if ap.empty:
                    pontos_val = 0
                    data_envio = None
                    acerto_11 = 0
                    # Primeira prova sem base
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        first_no_base_flags[int(u['id'])] = True
                else:
                    p_list = calcular_pontuacao_lote(ap, ress, provs)
                    pontos_val = sum(p_list) if p_list else 0
                    data_envio = ap.iloc[0].get('data_envio', None)
                    acerto_11 = 1 if ap.iloc[0]['piloto_11'] == piloto_11_real else 0
                    # Primeira prova com aposta automática (sem base)
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        try:
                            if int(ap.iloc[0].get('automatica', 0)) > 0:
                                first_no_base_flags[int(u['id'])] = True
                        except Exception:
                            pass
                
                tab.append({
                    'usuario_id': u['id'],
                    'pontos': pontos_val,
                    'data_envio': data_envio,
                    'acerto_11': acerto_11
                })

            # Aplicar regra de 85% do pior pontuador na primeira corrida sem base
            if first_no_base_flags:
                try:
                    pontos_validos = [
                        t['pontos'] for t in tab
                        if t['pontos'] is not None and not first_no_base_flags.get(int(t['usuario_id']), False)
                    ]
                    pior_pontuador = min(pontos_validos) if pontos_validos else 0
                except Exception:
                    pior_pontuador = 0
                for t in tab:
                    if first_no_base_flags.get(int(t['usuario_id']), False):
                        t['pontos'] = round(pior_pontuador * 0.85, 2)
            
            df = pd.DataFrame(tab)
            df['data_envio'] = pd.to_datetime(df['data_envio'], errors='coerce')
            df = df.sort_values(
                by=['pontos', 'acerto_11', 'data_envio'],
                ascending=[False, False, True]
            ).reset_index(drop=True)
            df['posicao'] = df.index + 1
            salvar_classificacao_prova(pid, df, temporada_prova)
