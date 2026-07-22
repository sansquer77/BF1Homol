"""Notificacoes de resultado de prova para participantes."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from services.bets_scoring import calcular_pontuacao_lote
from services.data_access_apostas import get_apostas_df, get_participantes_temporada_df
from services.data_access_provas import get_provas_df, get_resultados_df
from services.email_service import enviar_email
from utils.html_utils import escape_html_attr, escape_html_text
from services.rules_service import get_regras_aplicaveis
from utils.helpers import get_bf1_logo_data_uri
from utils.logging_utils import redact_identifier

logger = logging.getLogger(__name__)


@dataclass
class ResultadoEmailStats:
    enviados: int = 0
    falhas: int = 0
    sem_aposta: int = 0


def _parse_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = ast.literal_eval(str(raw or "{}"))
        except Exception:
            return {}
    if not isinstance(parsed, dict):
        return {}
    normalizado = {}
    for chave, valor in parsed.items():
        try:
            normalizado[int(chave)] = valor
        except Exception:
            normalizado[chave] = valor
    return normalizado


def _tipo_prova(prova_nome: str, tipo_raw: Any) -> str:
    tipo = str(tipo_raw or "").strip()
    if tipo.lower() == "sprint" or "sprint" in str(prova_nome or "").lower():
        return "Sprint"
    return "Normal"


def _pontos_lista(temporada: str, tipo_prova: str, regras: dict) -> list[float]:
    pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]
    if tipo_prova == "Sprint":
        return list(regras.get("pontos_sprint_posicoes") or regras.get("pontos_posicoes") or pontos_sprint)
    return list(regras.get("pontos_posicoes") or pontos_f1)


def _detalhar_aposta_resultado(
    aposta: pd.Series,
    prova: pd.Series,
    resultado: pd.Series,
    temporada: str,
) -> dict:
    prova_nome = str(aposta.get("nome_prova") or prova.get("nome") or "Prova")
    tipo_prova = _tipo_prova(prova_nome, prova.get("tipo", "Normal"))
    regras = get_regras_aplicaveis(temporada, tipo_prova)
    pontos_por_posicao = _pontos_lista(temporada, tipo_prova, regras)
    posicoes_dict = _parse_dict(resultado.get("posicoes"))
    piloto_para_pos = {str(v).strip(): int(k) for k, v in posicoes_dict.items() if str(v).strip()}

    pilotos_apostados = [p.strip() for p in str(aposta.get("pilotos", "")).split(",") if p.strip()]
    fichas = []
    for raw in str(aposta.get("fichas", "")).split(","):
        try:
            fichas.append(int(raw))
        except Exception:
            fichas.append(0)

    abandonos: set[str] = set()
    if regras.get("penalidade_abandono") and "abandono_pilotos" in resultado.index:
        raw_aband = resultado.get("abandono_pilotos", "") or ""
        abandonos = {p.strip() for p in str(raw_aband).split(",") if p and p.strip()}

    linhas = []
    total_pontos = 0.0
    for idx, piloto in enumerate(pilotos_apostados):
        ficha = fichas[idx] if idx < len(fichas) else 0
        pos_real = piloto_para_pos.get(str(piloto).strip())
        pontos = 0.0
        if pos_real is not None and 1 <= pos_real <= len(pontos_por_posicao):
            pontos = float(ficha) * float(pontos_por_posicao[pos_real - 1])
            total_pontos += pontos
        linhas.append(
            {
                "piloto": piloto,
                "fichas": ficha,
                "posicao_real": str(pos_real) if pos_real is not None else "-",
                "dnf": "DNF" if str(piloto).strip() in abandonos else "-",
                "pontos": pontos,
            }
        )

    piloto_11_apostado = str(aposta.get("piloto_11", "") or "").strip()
    piloto_11_real = str(posicoes_dict.get(11, "") or "").strip()
    bonus_11 = float(regras.get("pontos_11_colocado", 25) or 0)
    pontos_11 = bonus_11 if piloto_11_apostado == piloto_11_real else 0.0
    total_pontos += pontos_11

    penalidade_abandono = 0.0
    pilotos_abandonados = []
    if abandonos:
        pilotos_abandonados = [p for p in pilotos_apostados if p.strip() in abandonos]
        penalidade_abandono = float(regras.get("pontos_penalidade", 0) or 0) * len(pilotos_abandonados)
        total_pontos -= penalidade_abandono

    if tipo_prova == "Sprint" and regras.get("pontos_dobrada"):
        total_pontos *= 2

    penalidade_auto = 0.0
    try:
        automatica = int(aposta.get("automatica", 0) or 0)
    except Exception:
        automatica = 0
    if automatica >= 2:
        fator = max(0, 1 - (float(regras.get("penalidade_auto_percent", 20) or 20) / 100))
        total_com_desconto = round(total_pontos * fator, 2)
        penalidade_auto = round(total_pontos - total_com_desconto, 2)
        total_pontos = total_com_desconto

    return {
        "prova_nome": prova_nome,
        "tipo_prova": tipo_prova,
        "linhas": linhas,
        "piloto_11_apostado": piloto_11_apostado,
        "piloto_11_real": piloto_11_real,
        "pontos_11": pontos_11,
        "penalidade_abandono": penalidade_abandono,
        "pilotos_abandonados": pilotos_abandonados,
        "penalidade_auto": penalidade_auto,
        "total_pontos": round(float(total_pontos), 2),
    }


def _menor_pontuacao_descarte(
    usuario_id: int,
    temporada: str,
    apostas_df: pd.DataFrame,
    provas_df: pd.DataFrame,
    resultados_df: pd.DataFrame,
) -> dict | None:
    regras_temporada = get_regras_aplicaveis(temporada, "Normal")
    if not regras_temporada.get("descarte", False):
        return None

    apostas_part = apostas_df[apostas_df["usuario_id"] == usuario_id]
    if "temporada" in apostas_part.columns:
        apostas_part = apostas_part[apostas_part["temporada"] == temporada]
    if apostas_part.empty:
        return None

    pontos_por_prova = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df, temporada_descarte=temporada)
    provas_pontos = []
    for idx, (_, aposta) in enumerate(apostas_part.iterrows()):
        if idx >= len(pontos_por_prova) or pontos_por_prova[idx] is None:
            continue
        provas_pontos.append(
            {
                "nome_prova": str(aposta.get("nome_prova") or "Prova"),
                "pontos": float(pontos_por_prova[idx] or 0),
            }
        )
    if not provas_pontos:
        return None
    return min(provas_pontos, key=lambda item: item["pontos"])


def _montar_corpo_email(nome_usuario: str, detalhes: dict, descarte: dict | None) -> str:
    logo_uri = get_bf1_logo_data_uri()
    logo_uri_safe = escape_html_attr(logo_uri)
    linhas_html = "".join(
        (
            "<tr>"
            f"<td>{escape_html_text(linha['piloto'])}</td>"
            f"<td>{int(linha['fichas'])}</td>"
            f"<td>{escape_html_text(linha['posicao_real'])}</td>"
            f"<td>{escape_html_text(linha['dnf'])}</td>"
            f"<td>{float(linha['pontos']):.2f}</td>"
            "</tr>"
        )
        for linha in detalhes["linhas"]
    )
    descarte_html = ""
    if descarte:
        descarte_html = f"""
            <div class="notice">
                <p>Sua prova com menor pontuação será descartada no cálculo final do campeonato:</p>
                <p><strong>{escape_html_text(descarte['nome_prova'])}</strong> - {float(descarte['pontos']):.2f} pontos</p>
            </div>
        """

    penalidade_abandono_html = ""
    if detalhes["penalidade_abandono"]:
        pilotos = ", ".join(detalhes["pilotos_abandonados"])
        penalidade_abandono_html = (
            f"<p><strong>Penalidade por abandono (DNF):</strong> "
            f"{escape_html_text(pilotos)} - -{float(detalhes['penalidade_abandono']):.2f} pontos</p>"
        )
    penalidade_auto_html = ""
    if detalhes["penalidade_auto"]:
        penalidade_auto_html = f"<p><strong>Penalidade aposta automática:</strong> -{float(detalhes['penalidade_auto']):.2f}</p>"

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultado da Prova BF1</title>
    <style>
        body {{ font-family: Arial, sans-serif; background:#f5f5f5; margin:0; padding:0; color:#333; }}
        .container {{ max-width: 720px; margin: 0 auto; background:#fff; border-radius:8px; overflow:hidden; }}
        .header {{ text-align:center; padding:20px; border-bottom:1px solid #e0e0e0; }}
        .logo {{ width:100px; height:auto; }}
        .content {{ padding:28px; }}
        h1 {{ font-size:22px; margin:0 0 8px; }}
        h2 {{ font-size:18px; margin:20px 0 10px; }}
        table {{ border-collapse: collapse; width:100%; margin:16px 0; }}
        th, td {{ border:1px solid #ddd; padding:10px; text-align:left; font-size:14px; }}
        th {{ background:#f1f3f5; }}
        .total {{ font-size:17px; margin-top:16px; }}
        .notice {{ background:#fff3cd; border-left:4px solid #ffc107; padding:14px; margin:20px 0; }}
        .footer {{ background:#f5f5f5; padding:18px; text-align:center; font-size:12px; color:#666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><img src="{logo_uri_safe}" alt="BF1 Logo" class="logo"></div>
        <div class="content">
            <p>Olá, {escape_html_text(nome_usuario or "Participante")}!</p>
            <h1>Resultado cadastrado: {escape_html_text(detalhes["prova_nome"])}</h1>
            <p>Confira sua pontuação na prova ({escape_html_text(detalhes["tipo_prova"])}).</p>
            <table>
                <thead>
                    <tr>
                        <th>Piloto Apostado</th>
                        <th>Fichas</th>
                        <th>Posição Real</th>
                        <th>DNF</th>
                        <th>Pontos</th>
                    </tr>
                </thead>
                <tbody>{linhas_html}</tbody>
            </table>
            <p><strong>11º Apostado:</strong> {escape_html_text(detalhes["piloto_11_apostado"])} | <strong>11º Real:</strong> {escape_html_text(detalhes["piloto_11_real"])} | <strong>Pontos 11º:</strong> {float(detalhes["pontos_11"]):.0f}</p>
            {penalidade_abandono_html}
            {penalidade_auto_html}
            <p class="total"><strong>Total de Pontos na Prova:</strong> {float(detalhes["total_pontos"]):.2f}</p>
            {descarte_html}
        </div>
        <div class="footer">
            <p>Equipe de Organização BF1</p>
            <p>Este é um alerta automático após atualização de resultado.</p>
        </div>
    </div>
</body>
</html>
"""


def enviar_emails_resultado_prova(prova_id: int, temporada: str) -> ResultadoEmailStats:
    """Envia o resumo de resultado da prova para participantes com aposta cadastrada."""
    stats = ResultadoEmailStats()
    provas_df = get_provas_df(temporada)
    resultados_df = get_resultados_df(temporada)
    apostas_df = get_apostas_df(temporada)
    participantes_df = get_participantes_temporada_df(temporada)

    prova_row = provas_df[provas_df["id"] == prova_id]
    resultado_row = resultados_df[resultados_df["prova_id"] == prova_id]
    if prova_row.empty or resultado_row.empty:
        logger.warning("Email de resultado abortado: prova/resultado nao encontrado. prova_id=%s temporada=%s", prova_id, temporada)
        return stats

    apostas_prova = apostas_df[apostas_df["prova_id"] == prova_id]
    if "temporada" in apostas_prova.columns:
        apostas_prova = apostas_prova[apostas_prova["temporada"] == temporada]

    for _, participante in participantes_df.iterrows():
        usuario_id = int(participante.get("id"))
        email_destino = str(participante.get("email", "") or "").strip()
        aposta_usuario = apostas_prova[apostas_prova["usuario_id"] == usuario_id]
        if aposta_usuario.empty:
            stats.sem_aposta += 1
            continue
        if not email_destino:
            stats.falhas += 1
            logger.warning("Participante sem email para resultado. usuario_id=%s prova_id=%s", usuario_id, prova_id)
            continue

        detalhes = _detalhar_aposta_resultado(
            aposta_usuario.iloc[0],
            prova_row.iloc[0],
            resultado_row.iloc[0],
            temporada,
        )
        descarte = _menor_pontuacao_descarte(usuario_id, temporada, apostas_df, provas_df, resultados_df)
        corpo = _montar_corpo_email(str(participante.get("nome", "Participante")), detalhes, descarte)
        assunto = f"Resultado da prova - {detalhes['prova_nome']}"
        if enviar_email(email_destino, assunto, corpo):
            stats.enviados += 1
        else:
            stats.falhas += 1
            logger.warning(
                "Falha ao enviar email de resultado para %s (prova_id=%s)",
                redact_identifier(email_destino),
                prova_id,
            )

    return stats


__all__ = ["ResultadoEmailStats", "enviar_emails_resultado_prova"]
