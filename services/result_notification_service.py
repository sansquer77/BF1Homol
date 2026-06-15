"""Notificacoes de resultado de prova para participantes."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass

import pandas as pd

from services.bets_scoring import (
    calcular_pontuacao_detalhada_lote,
    detalhar_pontuacao_aposta,
)
from services.data_access_apostas import get_apostas_df, get_participantes_temporada_df
from services.data_access_provas import get_provas_df, get_resultados_df
from services.email_service import enviar_email
from services.rules_service import get_regras_aplicaveis
from utils.helpers import get_bf1_logo_data_uri
from utils.logging_utils import redact_identifier

logger = logging.getLogger(__name__)


@dataclass
class ResultadoEmailStats:
    enviados: int = 0
    falhas: int = 0
    sem_aposta: int = 0


def _mapear_descartes_por_usuario(
    temporada: str,
    apostas_df: pd.DataFrame,
    provas_df: pd.DataFrame,
    resultados_df: pd.DataFrame,
) -> dict[int, dict]:
    regras_temporada = get_regras_aplicaveis(temporada, "Normal")
    if not regras_temporada.get("descarte", False) or apostas_df.empty:
        return {}

    apostas_temp = apostas_df
    if "temporada" in apostas_temp.columns:
        apostas_temp = apostas_temp[apostas_temp["temporada"] == temporada]
    if apostas_temp.empty:
        return {}

    detalhes_por_prova = calcular_pontuacao_detalhada_lote(
        apostas_temp,
        resultados_df,
        provas_df,
        temporada=temporada,
    )
    descartes: dict[int, dict] = {}
    for idx, (_, aposta) in enumerate(apostas_temp.iterrows()):
        if idx >= len(detalhes_por_prova) or detalhes_por_prova[idx] is None:
            continue
        usuario_id = int(aposta.get("usuario_id"))
        candidato = {
            "nome_prova": str(aposta.get("nome_prova") or "Prova"),
            "pontos": float(detalhes_por_prova[idx]["total_pontos"] or 0),
        }
        atual = descartes.get(usuario_id)
        if atual is None or candidato["pontos"] < atual["pontos"]:
            descartes[usuario_id] = candidato
    return descartes


def _montar_corpo_email(nome_usuario: str, detalhes: dict, descarte: dict | None) -> str:
    logo_uri = get_bf1_logo_data_uri()
    linhas_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(linha['piloto'])}</td>"
            f"<td>{int(linha['fichas'])}</td>"
            f"<td>{html.escape(str(linha['posicao_real']))}</td>"
            f"<td>{html.escape(str(linha['dnf']))}</td>"
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
                <p><strong>{html.escape(descarte['nome_prova'])}</strong> - {float(descarte['pontos']):.2f} pontos</p>
            </div>
        """

    penalidade_abandono_html = ""
    if detalhes["penalidade_abandono"]:
        pilotos = ", ".join(detalhes["pilotos_abandonados"])
        penalidade_abandono_html = (
            f"<p><strong>Penalidade por abandono (DNF):</strong> "
            f"{html.escape(pilotos)} - -{float(detalhes['penalidade_abandono']):.2f} pontos</p>"
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
        <div class="header"><img src="{logo_uri}" alt="BF1 Logo" class="logo"></div>
        <div class="content">
            <p>Olá, {html.escape(nome_usuario or "Participante")}!</p>
            <h1>Resultado cadastrado: {html.escape(detalhes["prova_nome"])}</h1>
            <p>Confira sua pontuação na prova ({html.escape(detalhes["tipo_prova"])}).</p>
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
            <p><strong>11º Apostado:</strong> {html.escape(detalhes["piloto_11_apostado"])} | <strong>11º Real:</strong> {html.escape(detalhes["piloto_11_real"])} | <strong>Pontos 11º:</strong> {float(detalhes["pontos_11"]):.0f}</p>
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
    descartes_por_usuario = _mapear_descartes_por_usuario(temporada, apostas_df, provas_df, resultados_df)

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

        detalhes = detalhar_pontuacao_aposta(
            aposta_usuario.iloc[0],
            prova_row.iloc[0],
            resultado_row.iloc[0],
            temporada,
        )
        descarte = descartes_por_usuario.get(usuario_id)
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
