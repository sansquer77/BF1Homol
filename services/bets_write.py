"""Operações de escrita de apostas."""

from __future__ import annotations

import hashlib
import html
import logging
import math
import random
from datetime import datetime
from typing import Callable, Optional, Union, cast

import pandas as pd

from db.db_utils import db_connect
from db.db_schema import get_table_columns
from db.repo_bets import get_apostas_df
from db.repo_races import get_horario_prova, get_pilotos_df, get_provas_df, get_resultados_df
from db.repo_users import get_user_by_id
from db.repo_logs import registrar_log_aposta
from services.bets_ai import (
    _gerar_aposta_perplexity,
    _get_contexto_temporada_atual_ergast,
    _get_resumo_cenario_campeonato,
    _get_resumo_ultimas_apostas,
)
from services.bets_rules import ajustar_aposta_para_regras
from services.bets_rules import _aposta_valida_regras, pode_fazer_aposta
from services.email_service import enviar_email, gerar_analise_aposta_com_probabilidade
from services.rules_service import get_regras_aplicaveis
from utils.datetime_utils import now_sao_paulo
from utils.input_models import BetSubmissionInput, ValidationError
from utils.logging_utils import redact_identifier
from utils.request_utils import get_client_ip

logger = logging.getLogger(__name__)


def gerar_aposta_aleatoria(pilotos_df):
    if not pilotos_df.empty and "status" in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df["status"] == "Ativo"])
    equipes_unicas = [e for e in pilotos_df["equipe"].unique().tolist() if e]
    if len(equipes_unicas) < 3 or pilotos_df.empty:
        return [], [], None

    equipes_selecionadas = random.sample(equipes_unicas, min(5, len(equipes_unicas)))
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df["equipe"] == equipe]["nome"].tolist()
        if pilotos_equipe:
            pilotos_sel.append(random.choice(pilotos_equipe))

    if len(pilotos_sel) < 3:
        return [], [], None

    num_pilotos = len(pilotos_sel)
    fichas = [1] * num_pilotos
    fichas_restantes = 15 - num_pilotos
    for _ in range(fichas_restantes):
        idx = random.randint(0, num_pilotos - 1)
        fichas[idx] += 1

    todos_pilotos = pilotos_df["nome"].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)
    return pilotos_sel, fichas, piloto_11


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

    vr_set = {_norm_nome_piloto(row.get("n")) for row in vr if isinstance(vr, list) if _norm_nome_piloto(row.get("n"))}

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

        mu = mu - (0.20 * float(delta)) + ajuste_vr

        dnf_rate = 0.0
        if isinstance(dnf, dict):
            try:
                dnf_rate = float(dnf.get(nome_key, 0.0) or 0.0)
            except Exception:
                dnf_rate = 0.0
        mu += _clamp(dnf_rate, 0.0, 0.8) * 4.0
        mu = _clamp(mu, 1.0, float(n_pos))

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
        melhor_escolha = []
        usadas: set[int] = set()
        for row in probs_top:
            ordem = sorted(range(1, n_pos + 1), key=lambda p: row[p - 1], reverse=True)
            pos_sel = next((p for p in ordem if p not in usadas), ordem[0])
            melhor_escolha.append(pos_sel)
            usadas.add(pos_sel)

    pontos_estimados = 0.0
    detalhes_linhas: list[str] = []
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


def gerar_aposta_aleatoria_com_regras(pilotos_df, regras: dict):
    if not pilotos_df.empty and "status" in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df["status"] == "Ativo"])
    if pilotos_df.empty:
        return [], [], None
    equipes_unicas = [e for e in pilotos_df["equipe"].unique().tolist() if e]
    min_pilotos = int(regras.get("qtd_minima_pilotos") or regras.get("min_pilotos", 3))
    qtd_fichas = int(regras.get("quantidade_fichas", 15))
    fichas_max = int(regras.get("fichas_por_piloto", qtd_fichas))
    permite_mesma_equipe = bool(regras.get("mesma_equipe", False))

    pilotos_necessarios_por_cap = max(1, math.ceil(qtd_fichas / max(1, fichas_max)))
    alvo_pilotos = max(min_pilotos, pilotos_necessarios_por_cap)

    pilotos_sel = []
    if len(equipes_unicas) >= alvo_pilotos:
        equipes_selecionadas = random.sample(equipes_unicas, alvo_pilotos)
        for equipe in equipes_selecionadas:
            pilotos_equipe = pilotos_df[pilotos_df["equipe"] == equipe]["nome"].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
    else:
        if not permite_mesma_equipe:
            return [], [], None
        for equipe in equipes_unicas:
            pilotos_equipe = pilotos_df[pilotos_df["equipe"] == equipe]["nome"].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
        todos_pilotos = pilotos_df["nome"].tolist()
        safety = 10000
        while len(pilotos_sel) < alvo_pilotos and safety > 0:
            safety -= 1
            candidato = random.choice(todos_pilotos)
            if candidato not in pilotos_sel:
                pilotos_sel.append(candidato)
        if len(pilotos_sel) < alvo_pilotos:
            return [], [], None

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

    todos_pilotos = pilotos_df["nome"].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)
    return pilotos_sel, fichas, piloto_11


def _determinar_tipo_prova(prova_row: Union[pd.Series, dict], nome_prova: Optional[str]) -> str:
    try:
        if isinstance(prova_row, dict):
            t = prova_row.get("tipo")
        else:
            t = prova_row["tipo"] if "tipo" in prova_row and pd.notna(prova_row["tipo"]) else None
    except Exception:
        t = None
    if t and str(t).strip().lower() == "sprint":
        return "Sprint"
    if nome_prova and "sprint" in str(nome_prova).lower():
        return "Sprint"
    return "Normal"


def salvar_aposta(
    usuario_id,
    prova_id,
    pilotos,
    fichas,
    piloto_11,
    nome_prova,
    automatica=0,
    horario_forcado=None,
    temporada: Optional[str] = None,
    show_errors=True,
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

    try:
        prov_df = get_provas_df(temporada)
        tipo_col = None
        if not prov_df.empty:
            row = prov_df[prov_df["id"] == prova_id]
            if not row.empty and "tipo" in row.columns and pd.notna(row.iloc[0]["tipo"]):
                tipo_col = str(row.iloc[0]["tipo"]).strip()
        tipo_prova_regra = "Sprint" if (tipo_col and tipo_col.lower() == "sprint") or ("sprint" in str(nome_prova_bd).lower()) else "Normal"
    except Exception:
        tipo_prova_regra = "Sprint" if "sprint" in str(nome_prova_bd).lower() else "Normal"
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova_regra)

    quantidade_fichas = regras.get("quantidade_fichas", 15)
    min_pilotos = regras.get("min_pilotos", 3)
    max_por_piloto = int(regras.get("fichas_por_piloto", quantidade_fichas))

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < min_pilotos or sum(fichas) != quantidade_fichas or (fichas and max(fichas) > max_por_piloto):
        msg = f"Regra exige: mín {min_pilotos} pilotos, total {quantidade_fichas} fichas, máx {max_por_piloto} por piloto."
        _report_error(f"Dados inválidos para aposta. {msg}")
        return False

    _, _, horario_limite = pode_fazer_aposta(data_prova, horario_prova, horario_forcado or now_sao_paulo())
    agora_sp = horario_forcado or now_sao_paulo()
    tipo_aposta = 0 if horario_limite and (agora_sp <= horario_limite) else 1

    dados_pilotos = ", ".join(pilotos)
    dados_fichas = ", ".join(map(str, fichas))
    ip_apostador = get_client_ip()

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        _report_error(f"Usuário não encontrado: id={usuario_id}")
        return False
    status_usuario = str(usuario.get("status", "")).strip().lower()
    if status_usuario and status_usuario != "ativo":
        _report_error("Usuário inativo não pode efetuar apostas.")
        return False

    try:
        with db_connect() as conn:
            c = conn.cursor()
            aposta_cols = get_table_columns(conn, "apostas")

            if temporada is None:
                temporada = str(datetime.now().year)

            if tipo_aposta == 0 or permitir_salvar_tardia:
                if "temporada" in aposta_cols:
                    c.execute("DELETE FROM apostas WHERE usuario_id=%s AND prova_id=%s AND temporada=%s", (usuario_id, prova_id, temporada))
                else:
                    c.execute("DELETE FROM apostas WHERE usuario_id=%s AND prova_id=%s", (usuario_id, prova_id))

                data_envio = agora_sp.isoformat()
                if "temporada" in aposta_cols:
                    c.execute(
                        """
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica, temporada)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            usuario_id,
                            prova_id,
                            data_envio,
                            ",".join(pilotos),
                            ",".join(map(str, fichas)),
                            piloto_11,
                            nome_prova_bd,
                            automatica,
                            temporada,
                        ),
                    )
                else:
                    c.execute(
                        """
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            usuario_id,
                            prova_id,
                            data_envio,
                            ",".join(pilotos),
                            ",".join(map(str, fichas)),
                            piloto_11,
                            nome_prova_bd,
                            automatica,
                        ),
                    )
            else:
                _report_error("Aposta fora do horário limite.")
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
                    nome_usuario=usuario.get("nome", ""),
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

                if probabilidade_combinada is not None:
                    probabilidade = probabilidade_combinada

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
                    nome_usuario=str(usuario.get("nome", "Participante")),
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
                    previsao_html += f"<p><b>Estimativa de pontos:</b> {float(pontos_estimados):.1f}</p>"
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
                    redact_identifier(str(usuario.get("email", ""))),
                    e,
                )

            try:
                email_ok = enviar_email(usuario["email"], f"Aposta registrada - {nome_prova_bd}", corpo_email)
                if not email_ok:
                    logger.warning(
                        "Falha de envio de email de aposta para %s (prova_id=%s)",
                        redact_identifier(str(usuario.get("email", ""))),
                        prova_id,
                    )
            except Exception as e:
                logger.warning(
                    "Falha ao enviar email de aposta para %s: %s",
                    redact_identifier(str(usuario.get("email", ""))),
                    e,
                )

    except Exception as e:
        _report_error("Erro ao salvar aposta.")
        logger.exception("Erro ao salvar aposta: %s", e)
        return False

    registrar_log_aposta(
        usuario_id=usuario_id,
        prova_id=prova_id,
        apostador=usuario["nome"],
        pilotos=dados_pilotos,
        aposta=dados_fichas,
        nome_prova=nome_prova_bd,
        piloto_11=piloto_11,
        tipo_aposta=tipo_aposta,
        automatica=automatica,
        horario=agora_sp,
        ip_address=ip_apostador,
        temporada=temporada,
        status="Registrada",
    )
    return True


def gerar_aposta_automatica(usuario_id, prova_id, nome_prova, apostas_df, provas_df, temporada=None):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"

    prova_atual = provas_df[provas_df["id"] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."

    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)

    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id)
        & (apostas_df["prova_id"] == prova_id)
        & ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."

    ap_ant = pd.DataFrame()
    prova_id_min = None
    try:
        prova_id_min = int(provas_df["id"].min()) if not provas_df.empty else None
    except Exception:
        prova_id_min = None

    try:
        provas_tmp = provas_df.copy()
        if "data" in provas_tmp.columns:
            provas_tmp["__data_dt"] = pd.to_datetime(provas_tmp["data"], errors="coerce")
        else:
            provas_tmp["__data_dt"] = pd.NaT
        provas_tmp["__hora_str"] = provas_tmp.get("horario_prova", "00:00:00")
        provas_tmp["__hora_dt"] = pd.to_datetime(provas_tmp["__hora_str"], format="%H:%M:%S", errors="coerce")
        provas_tmp["__hora_dt"] = provas_tmp["__hora_dt"].fillna(pd.to_datetime("00:00:00", format="%H:%M:%S"))
        provas_tmp["__prova_dt"] = (
            provas_tmp["__data_dt"]
            + pd.to_timedelta(provas_tmp["__hora_dt"].dt.hour, unit="h")
            + pd.to_timedelta(provas_tmp["__hora_dt"].dt.minute, unit="m")
            + pd.to_timedelta(provas_tmp["__hora_dt"].dt.second, unit="s")
        )
        provas_tmp = provas_tmp.sort_values(["__prova_dt", "id"])

        prova_atual_row = provas_tmp[provas_tmp["id"] == prova_id]
        if not prova_atual_row.empty:
            prova_atual_dt = prova_atual_row.iloc[0]["__prova_dt"]
            provas_anteriores = provas_tmp[provas_tmp["__prova_dt"] < prova_atual_dt]
            if not provas_anteriores.empty:
                prova_ant_id = int(provas_anteriores.iloc[-1]["id"])
                ap_ant = apostas_df[(apostas_df["usuario_id"] == usuario_id) & (apostas_df["prova_id"] == prova_ant_id)]
    except Exception:
        ap_ant = pd.DataFrame()

    if ap_ant.empty:
        try:
            provas_sorted = provas_df.sort_values("id")
            prev_rows = provas_sorted[provas_sorted["id"] < prova_id]
            if not prev_rows.empty:
                prova_ant_id = int(prev_rows.iloc[-1]["id"])
                ap_ant = apostas_df[(apostas_df["usuario_id"] == usuario_id) & (apostas_df["prova_id"] == prova_ant_id)]
        except Exception:
            ap_ant = pd.DataFrame()

    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and "status" in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df["status"] == "Ativo"])

    if not ap_ant.empty:
        ap_ant = ap_ant.iloc[0]
        pilotos_ant = [p.strip() for p in ap_ant["pilotos"].split(",")]
        fichas_ant = list(map(int, ap_ant["fichas"].split(",")))
        piloto_11_ant = ap_ant["piloto_11"].strip()
        pilotos_aj, fichas_aj = ajustar_aposta_para_regras(pilotos_ant, fichas_ant, regras, pilotos_df)
        if not pilotos_aj:
            pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        else:
            pilotos_ant, fichas_ant = pilotos_aj, fichas_aj
    else:
        if prova_id_min is not None and prova_id != prova_id_min:
            return False, "Sem aposta anterior para copiar. Gere apenas na primeira prova."
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)

    if not pilotos_ant:
        return False, "Não há dados válidos para gerar aposta automática."

    faltas_atuais = 0
    with db_connect() as conn:
        c = conn.cursor()
        cols_usuarios = get_table_columns(conn, "usuarios")
        if "faltas" in cols_usuarios:
            c.execute("SELECT COALESCE(faltas, 0) AS faltas FROM usuarios WHERE id=%s", (usuario_id,))
            row = c.fetchone()
            faltas_atuais = int((row or {}).get("faltas", 0) or 0)
    nova_auto = faltas_atuais + 1

    sucesso = salvar_aposta(
        usuario_id,
        prova_id,
        pilotos_ant,
        fichas_ant,
        piloto_11_ant,
        nome_prova,
        automatica=nova_auto,
        temporada=temporada,
        show_errors=False,
        permitir_salvar_tardia=True,
    )

    if not sucesso:
        return False, "Falha ao salvar."

    with db_connect() as conn:
        c = conn.cursor()
        cols_usuarios = get_table_columns(conn, "usuarios")
        if "faltas" in cols_usuarios:
            c.execute("UPDATE usuarios SET faltas = COALESCE(faltas, 0) + 1 WHERE id=%s", (usuario_id,))
            conn.commit()

    return True, "Aposta automática gerada!"


def gerar_aposta_sem_ideias(usuario_id, prova_id, nome_prova, temporada=None):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"

    provas_df = get_provas_df(temporada)
    prova_atual = provas_df[provas_df["id"] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."

    data_prova = str(prova_atual["data"].iloc[0])
    horario_prova = str(prova_atual["horario_prova"].iloc[0])
    pode, msg, _ = pode_fazer_aposta(data_prova, horario_prova)
    if not pode:
        return False, f"Aposta fora do prazo. {msg}"

    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)

    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and "status" in pilotos_df.columns:
        pilotos_df = cast(pd.DataFrame, pilotos_df[pilotos_df["status"] == "Ativo"])
    if pilotos_df.empty:
        return False, "Não há pilotos ativos para gerar aposta."

    apostas_df = get_apostas_df(temporada)
    resultados_df = get_resultados_df(temporada)
    ultimas_apostas = _get_resumo_ultimas_apostas(usuario_id, apostas_df, limite=2)
    cenario = _get_resumo_cenario_campeonato(resultados_df, provas_df, limite=2)
    contexto_ergast = _get_contexto_temporada_atual_ergast(temporada=str(temporada or datetime.now().year), nome_prova=nome_prova)

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

__all__ = [
    "salvar_aposta",
    "gerar_aposta_aleatoria",
    "gerar_aposta_aleatoria_com_regras",
    "ajustar_aposta_para_regras",
    "gerar_aposta_automatica",
    "gerar_aposta_sem_ideias",
]
