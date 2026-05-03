"""Serviço de consolidação histórica de apostas por participante.

Este módulo fornece funções puras de cálculo — sem acoplamento a Streamlit —
para alimentar a aba 'Histórico' do Painel do Participante.

Fonte de dados para pontuação:
    A tabela `posicoes_participantes` é a fonte oficial de pontuação.
    Ela é calculada e persistida por `bets_scoring.salvar_classificacao_prova`,
    que aplica TODAS as regras ativas da temporada (pontos por posição, bônus,
    penalidades, descarte, aposta automática etc.).

    Por isso, este serviço NÃO recalcula pontuação — apenas SOMA os pontos
    já calculados e armazenados, garantindo consistência com o que o
    participante viu na classificação durante a temporada.

Fonte de dados para acertos do 11º:
    A coluna `piloto_11` não está em `posicoes_participantes`, portanto
    os acertos são derivados comparando apostas x resultados diretamente
    da tabela `resultados`.

Responsabilidades:
    - Buscar apostas de TODAS as temporadas do participante
    - Calcular métricas de resumo (melhor colocação, melhor pontuação,
      médias, acertos 11º)
    - Agregar fichas por piloto e por temporada para o gráfico de barras
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# Importações alinhadas com o padrão do restante da aplicação:
# - get_apostas_df e get_posicoes_participantes_df vivem em db.repo_bets
# - get_resultados_df é exposto via services.data_access_provas
from db.repo_bets import get_apostas_df, get_posicoes_participantes_df
from services.data_access_provas import get_resultados_df


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
    apostas_todas = get_apostas_df()
    if apostas_todas.empty or "usuario_id" not in apostas_todas.columns:
        return []

    apostas_usuario = apostas_todas[apostas_todas["usuario_id"] == usuario_id]
    if apostas_usuario.empty or "temporada" not in apostas_usuario.columns:
        return []

    return (
        apostas_usuario["temporada"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )


def _get_posicao_final_de_temporada(
    posicoes_df: pd.DataFrame,
    usuario_id: int,
    temporada: str,
) -> Optional[int]:
    """Retorna a posição final do participante na última prova registrada da temporada.

    A colocação após a última prova com resultado equivale ao encerramento
    do campeonato quando os dados estão atualizados.

    Args:
        posicoes_df: DataFrame completo de posicoes_participantes (já filtrado
                     por temporada pelo chamador).
        usuario_id: ID do participante.
        temporada: Temporada de referência (usada apenas para log/depuração).

    Returns:
        Posição inteira ou None se não houver dados.
    """
    if posicoes_df.empty:
        return None

    part = posicoes_df[posicoes_df["usuario_id"] == usuario_id]
    if part.empty or "posicao" not in part.columns:
        return None

    ultima_prova = part["prova_id"].max()
    linha = part[part["prova_id"] == ultima_prova]
    return int(linha.iloc[0]["posicao"]) if not linha.empty else None


def _get_pontuacao_total_de_temporada(
    posicoes_df: pd.DataFrame,
    usuario_id: int,
) -> Optional[float]:
    """Soma os pontos já calculados em posicoes_participantes para o participante.

    Esta é a fonte oficial de pontuação — não recalcula nada, apenas agrega
    os valores que o serviço de classificação já persistiu aplicando todas
    as regras vigentes da temporada.

    Args:
        posicoes_df: DataFrame de posicoes_participantes filtrado por temporada.
        usuario_id: ID do participante.

    Returns:
        Total de pontos ou None se não houver registros.
    """
    if posicoes_df.empty or "pontos" not in posicoes_df.columns:
        return None

    part = posicoes_df[posicoes_df["usuario_id"] == usuario_id]
    if part.empty:
        return None

    return round(float(part["pontos"].sum()), 2)


def _parse_posicoes(raw: str) -> dict[int, str]:
    """Interpreta o campo `posicoes` da tabela resultados como dict {int -> str}.

    O campo é armazenado como representação Python de dicionário
    (ex.: ``{1: 'Hamilton', 2: 'Verstappen', ...}``). As chaves são normalizadas
    para ``int`` para garantir que buscas por posição numérica funcionem
    independentemente do formato original.

    Args:
        raw: String com a representação do dicionário de posições.

    Returns:
        Dicionário ``{posição: nome_do_piloto}`` com chaves inteiras.
        Retorna ``{}`` em caso de erro de parsing.
    """
    try:
        parsed = ast.literal_eval(raw)
        # Normaliza chaves para int — evita falsos negativos em posicoes.get(11)
        return {int(k): str(v).strip() for k, v in parsed.items()}
    except Exception:
        return {}


def _contar_acertos_11_em_temporada(
    apostas_df: pd.DataFrame,
    resultados_df: pd.DataFrame,
    usuario_id: int,
) -> int:
    """Conta quantas vezes o participante acertou o 11º colocado na temporada.

    O acerto do 11º não está em posicoes_participantes, portanto é derivado
    diretamente da comparação entre a aposta e o resultado.

    Args:
        apostas_df: Apostas do participante já filtradas por temporada e usuario_id.
        resultados_df: Resultados da temporada.
        usuario_id: ID do participante (reservado para validações futuras).

    Returns:
        Número de acertos do 11º colocado.
    """
    if apostas_df.empty or resultados_df.empty:
        return 0

    # Monta índice prova_id (int) -> piloto_11_real para evitar lookups repetidos
    piloto_11_por_prova: dict[int, str] = {}
    for _, resultado in resultados_df.iterrows():
        try:
            prova_id = int(resultado["prova_id"])
            posicoes = _parse_posicoes(resultado["posicoes"])
            piloto_11_por_prova[prova_id] = posicoes.get(11, "")
        except Exception:
            continue

    acertos = 0
    for _, aposta in apostas_df.iterrows():
        try:
            prova_id = int(aposta["prova_id"])
        except Exception:
            continue
        piloto_11_real = piloto_11_por_prova.get(prova_id, "")
        piloto_11_apostado = str(aposta.get("piloto_11", "")).strip()
        if piloto_11_apostado and piloto_11_apostado == piloto_11_real:
            acertos += 1

    return acertos


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def calcular_resumo_historico(usuario_id: int) -> ResumoHistorico:
    """Consolida métricas históricas de todas as temporadas do participante.

    Pontuação é lida diretamente de `posicoes_participantes`, garantindo que
    as regras de cada temporada (descarte, penalidades, aposta automática
    etc.) já estejam aplicadas.

    Args:
        usuario_id: ID do usuário autenticado.

    Returns:
        ResumoHistorico com as métricas calculadas.
    """
    temporadas = _get_todas_temporadas_do_participante(usuario_id)
    if not temporadas:
        return ResumoHistorico()

    posicoes_por_temporada: list[tuple[str, int]] = []
    pontuacoes_por_temporada: list[tuple[str, float]] = []
    total_acertos_11 = 0

    for temporada in sorted(temporadas):
        # Fonte oficial: pontos já calculados e persistidos pelo serviço de classificação
        posicoes_df = get_posicoes_participantes_df(temporada)

        posicao = _get_posicao_final_de_temporada(posicoes_df, usuario_id, temporada)
        if posicao is not None:
            posicoes_por_temporada.append((temporada, posicao))

        pontuacao = _get_pontuacao_total_de_temporada(posicoes_df, usuario_id)
        if pontuacao is not None:
            pontuacoes_por_temporada.append((temporada, pontuacao))

        # Acertos do 11º: não está em posicoes_participantes — precisa das apostas
        apostas_temp = get_apostas_df(temporada)
        apostas_part = (
            apostas_temp[apostas_temp["usuario_id"] == usuario_id]
            if not apostas_temp.empty
            else pd.DataFrame()
        )
        resultados_temp = get_resultados_df(temporada)
        total_acertos_11 += _contar_acertos_11_em_temporada(
            apostas_part, resultados_temp, usuario_id
        )

    resumo = ResumoHistorico(temporadas_com_dados=sorted(temporadas))
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
        resumo.melhor_pontuacao = melhor_pt[1]
        resumo.melhor_pontuacao_ano = melhor_pt[0]
        resumo.media_pontuacoes = round(
            sum(p for _, p in pontuacoes_por_temporada) / len(pontuacoes_por_temporada), 2
        )

    return resumo


def calcular_dados_grafico(usuario_id: int) -> DadosGrafico:
    """Agrega fichas apostadas por piloto e por temporada para o gráfico de barras.

    Usa TODAS as apostas do participante. As fichas são o dado original da
    aposta — não envolvem cálculo de pontuação, portanto lidas diretamente
    da tabela de apostas.

    Args:
        usuario_id: ID do usuário autenticado.

    Returns:
        DadosGrafico com fichas por temporada/piloto e o piloto mais apostado.
    """
    temporadas = _get_todas_temporadas_do_participante(usuario_id)
    if not temporadas:
        return DadosGrafico()

    fichas_por_temporada_piloto: dict[str, dict[str, int]] = {}
    fichas_totais_piloto: dict[str, int] = {}

    for temporada in sorted(temporadas):
        apostas_temp = get_apostas_df(temporada)
        if apostas_temp.empty:
            continue

        apostas_part = apostas_temp[apostas_temp["usuario_id"] == usuario_id]
        if apostas_part.empty:
            continue

        # setdefault apenas quando há apostas — evita temporadas fantasma no gráfico
        fichas_por_temporada_piloto.setdefault(temporada, {})

        for _, aposta in apostas_part.iterrows():
            try:
                pilotos = [p.strip() for p in str(aposta["pilotos"]).split(",") if p.strip()]
                fichas = [int(f) for f in str(aposta["fichas"]).split(",") if f.strip()]
            except Exception:
                continue

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
