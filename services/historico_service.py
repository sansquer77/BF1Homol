"""Serviço de consolidação histórica de apostas por participante.

Este módulo fornece funções puras de cálculo — sem acoplamento a Streamlit —
para alimentar a aba 'Histórico Geral' do Painel do Participante.

Responsabilidades:
- Buscar apostas de TODAS as temporadas do participante
- Calcular métricas de resumo (melhor colocação, melhor pontuação, médias, acertos 11º)
- Agregar fichas por piloto e por temporada para o gráfico de barras
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from db.repo_bets import get_apostas_df, get_posicoes_participantes_df
from services.bets_scoring import calcular_pontuacao_lote
from services.data_access_provas import get_provas_df, get_resultados_df


# ---------------------------------------------------------------------------
# Tipos de resultado
# ---------------------------------------------------------------------------

@dataclass
class ResumoHistorico:
    """Métricas consolidadas do participante em todas as temporadas."""

    melhor_colocacao: Optional[int] = None
    melhor_colocacao_ano: Optional[str] = None
    melhor_pontuacao: Optional[float] = None
    melhor_pontuacao_ano: Optional[str] = None
    media_posicoes: Optional[float] = None
    media_pontuacoes: Optional[float] = None
    total_acertos_11: int = 0
    temporadas_com_dados: list[str] = field(default_factory=list)


@dataclass
class DadosGrafico:
    """Dados preparados para o gráfico de barras de apostas por temporada."""

    # { temporada: { piloto: total_fichas } }
    fichas_por_temporada_piloto: dict[str, dict[str, int]] = field(default_factory=dict)
    piloto_mais_apostado: Optional[str] = None
    total_fichas_piloto_mais_apostado: int = 0


# ---------------------------------------------------------------------------
# Funções auxiliares privadas
# ---------------------------------------------------------------------------

def _get_todas_temporadas_do_participante(usuario_id: int) -> list[str]:
    """Retorna lista ordenada de temporadas em que o participante tem apostas."""
    apostas_todas = get_apostas_df()  # sem filtro de temporada
    if apostas_todas.empty or "usuario_id" not in apostas_todas.columns:
        return []

    apostas_usuario = apostas_todas[apostas_todas["usuario_id"] == usuario_id]
    if apostas_usuario.empty or "temporada" not in apostas_usuario.columns:
        return []

    temporadas = (
        apostas_usuario["temporada"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    return sorted(temporadas)


def _calcular_pontuacao_temporada(
    usuario_id: int,
    apostas_df: pd.DataFrame,
    temporada: str,
) -> Optional[float]:
    """Calcula a pontuação total do participante em uma temporada.

    Retorna None quando não há resultados cadastrados ainda.
    """
    provas_df = get_provas_df(temporada)
    resultados_df = get_resultados_df(temporada)

    apostas_part = apostas_df[
        (apostas_df["usuario_id"] == usuario_id)
        & (apostas_df["temporada"] == temporada)
    ]

    if apostas_part.empty or provas_df.empty or resultados_df.empty:
        return None

    pontos_lista = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df)
    pontos_validos = [p for p in pontos_lista if p is not None]
    return sum(pontos_validos) if pontos_validos else None


def _get_posicao_final_temporada(
    usuario_id: int,
    temporada: str,
) -> Optional[int]:
    """Retorna a melhor posição registrada em posicoes_participantes para o participante na temporada.

    Usa a posição da última prova com resultado, que equivale à colocação final
    quando os dados estão atualizados.
    """
    posicoes_df = get_posicoes_participantes_df(temporada)
    if posicoes_df.empty:
        return None

    posicoes_part = posicoes_df[posicoes_df["usuario_id"] == usuario_id]
    if posicoes_part.empty or "posicao" not in posicoes_part.columns:
        return None

    # A colocação final é a posição na última prova com resultado
    posicoes_part = posicoes_part.sort_values("prova_id", ascending=False)
    return int(posicoes_part.iloc[0]["posicao"])


def _contar_acertos_11_em_apostas(
    apostas_df: pd.DataFrame,
    temporada: str,
    usuario_id: int,
) -> int:
    """Conta acertos do 11º colocado em uma temporada para o participante."""
    resultados_df = get_resultados_df(temporada)
    if resultados_df.empty or apostas_df.empty:
        return 0

    apostas_part = apostas_df[
        (apostas_df["usuario_id"] == usuario_id)
        & (apostas_df["temporada"] == temporada)
    ]
    if apostas_part.empty:
        return 0

    import ast

    acertos = 0
    for _, aposta in apostas_part.iterrows():
        prova_id = aposta["prova_id"]
        resultado_row = resultados_df[resultados_df["prova_id"] == prova_id]
        if resultado_row.empty:
            continue
        try:
            posicoes_dict = ast.literal_eval(resultado_row.iloc[0]["posicoes"])
        except Exception:
            continue
        piloto_11_real = str(posicoes_dict.get(11, "")).strip()
        piloto_11_apostado = str(aposta.get("piloto_11", "")).strip()
        if piloto_11_apostado and piloto_11_apostado == piloto_11_real:
            acertos += 1

    return acertos


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def calcular_resumo_historico(usuario_id: int) -> ResumoHistorico:
    """Consolida métricas históricas de todas as temporadas do participante.

    Args:
        usuario_id: ID do usuário autenticado.

    Returns:
        ResumoHistorico com as métricas calculadas.
    """
    temporadas = _get_todas_temporadas_do_participante(usuario_id)
    if not temporadas:
        return ResumoHistorico()

    apostas_todas = get_apostas_df()

    posicoes_por_temporada: list[tuple[str, int]] = []
    pontuacoes_por_temporada: list[tuple[str, float]] = []
    total_acertos_11 = 0

    for temporada in temporadas:
        posicao = _get_posicao_final_temporada(usuario_id, temporada)
        if posicao is not None:
            posicoes_por_temporada.append((temporada, posicao))

        pontuacao = _calcular_pontuacao_temporada(usuario_id, apostas_todas, temporada)
        if pontuacao is not None:
            pontuacoes_por_temporada.append((temporada, pontuacao))

        total_acertos_11 += _contar_acertos_11_em_apostas(
            apostas_todas, temporada, usuario_id
        )

    resumo = ResumoHistorico(temporadas_com_dados=temporadas)
    resumo.total_acertos_11 = total_acertos_11

    if posicoes_por_temporada:
        melhor = min(posicoes_por_temporada, key=lambda x: x[1])
        resumo.melhor_colocacao = melhor[1]
        resumo.melhor_colocacao_ano = melhor[0]
        resumo.media_posicoes = round(
            sum(p for _, p in posicoes_por_temporada) / len(posicoes_por_temporada), 2
        )

    if pontuacoes_por_temporada:
        melhor_pt = max(pontuacoes_por_temporada, key=lambda x: x[1])
        resumo.melhor_pontuacao = round(melhor_pt[1], 2)
        resumo.melhor_pontuacao_ano = melhor_pt[0]
        resumo.media_pontuacoes = round(
            sum(p for _, p in pontuacoes_por_temporada) / len(pontuacoes_por_temporada), 2
        )

    return resumo


def calcular_dados_grafico(usuario_id: int) -> DadosGrafico:
    """Agrega fichas apostadas por piloto e por temporada para exibição em gráfico.

    Usa TODAS as apostas do participante, sem filtro de temporada.

    Args:
        usuario_id: ID do usuário autenticado.

    Returns:
        DadosGrafico com dicionário de fichas por temporada/piloto
        e informações do piloto mais apostado no total.
    """
    temporadas = _get_todas_temporadas_do_participante(usuario_id)
    if not temporadas:
        return DadosGrafico()

    apostas_todas = get_apostas_df()
    apostas_part = apostas_todas[apostas_todas["usuario_id"] == usuario_id]

    if apostas_part.empty:
        return DadosGrafico()

    fichas_por_temporada_piloto: dict[str, dict[str, int]] = {}
    fichas_totais_piloto: dict[str, int] = {}

    for _, aposta in apostas_part.iterrows():
        temporada = str(aposta.get("temporada", "")).strip()
        if not temporada:
            continue

        try:
            pilotos = [p.strip() for p in str(aposta["pilotos"]).split(",") if p.strip()]
            fichas = [int(f) for f in str(aposta["fichas"]).split(",") if f.strip()]
        except Exception:
            continue

        if temporada not in fichas_por_temporada_piloto:
            fichas_por_temporada_piloto[temporada] = {}

        for piloto, ficha in zip(pilotos, fichas):
            if ficha <= 0:
                continue
            fichas_por_temporada_piloto[temporada][piloto] = (
                fichas_por_temporada_piloto[temporada].get(piloto, 0) + ficha
            )
            fichas_totais_piloto[piloto] = fichas_totais_piloto.get(piloto, 0) + ficha

    dados = DadosGrafico(fichas_por_temporada_piloto=fichas_por_temporada_piloto)

    if fichas_totais_piloto:
        piloto_top = max(fichas_totais_piloto, key=lambda p: fichas_totais_piloto[p])
        dados.piloto_mais_apostado = piloto_top
        dados.total_fichas_piloto_mais_apostado = fichas_totais_piloto[piloto_top]

    return dados


__all__ = [
    "ResumoHistorico",
    "DadosGrafico",
    "calcular_resumo_historico",
    "calcular_dados_grafico",
]
