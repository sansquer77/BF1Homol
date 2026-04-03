import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Optional
from services.data_access_core import (
    db_connect,
    get_table_columns,
)
from services.data_access_apostas import (
    get_apostas_df,
    get_participantes_temporada_df,
)
from services.data_access_provas import (
    get_provas_df,
    get_resultados_df,
)
from services.data_access_auth import (
    usuarios_status_historico_disponivel,
)
from services.rules_service import get_regras_aplicaveis
from utils.helpers import render_page_header
from utils.season_utils import get_season_options, get_default_season_index


def _table_height(total_rows: int, row_height: int = 36, max_height: int = 560) -> int:
    return min(max_height, 42 + (max(total_rows, 1) * row_height))


def _normalizar_ids(df: pd.DataFrame, column: str = "id") -> pd.DataFrame:
    """Remove linhas com IDs inválidos e converte IDs para int."""
    if df.empty or column not in df.columns:
        return df
    df_norm = df.copy()
    df_norm[column] = pd.to_numeric(df_norm[column], errors="coerce")
    df_norm = df_norm[df_norm[column].notna()].copy()
    df_norm[column] = df_norm[column].astype(int)
    return df_norm


def _extrair_ids_validos(df: pd.DataFrame, column: str = "id") -> list[int]:
    """Extrai IDs numéricos válidos de forma defensiva."""
    if df.empty or column not in df.columns:
        return []
    ids = pd.to_numeric(df[column], errors="coerce").dropna().astype(int)
    return ids.tolist()


def _plot_colunas(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> None:
    """Renderiza gráfico de barras adaptando orientação para melhorar legibilidade."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return
    plot_df = df.copy()
    categorias = plot_df[x_col].astype(str).nunique()
    usar_horizontal = categorias >= 10

    if usar_horizontal:
        # Em listas longas, barras horizontais evitam corte de rótulos no eixo categórico.
        plot_df = plot_df.sort_values(y_col, ascending=True)
        fig = px.bar(
            plot_df,
            x=y_col,
            y=x_col,
            title=title,
            orientation='h',
            text=y_col,
        )
    else:
        plot_df = plot_df.sort_values(y_col, ascending=False)
        fig = px.bar(
            plot_df,
            x=x_col,
            y=y_col,
            title=title,
            text=y_col,
        )

    fig.update_traces(
        marker_color="#1f77b4",
        textposition="outside",
        cliponaxis=False,
    )
    if usar_horizontal:
        fig.update_layout(
            showlegend=False,
            xaxis_title=y_col,
            yaxis_title=x_col,
            margin=dict(t=70, r=30, l=190, b=40),
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True),
        )
    else:
        fig.update_layout(
            showlegend=False,
            xaxis_title=x_col,
            yaxis_title=y_col,
            margin=dict(t=70, r=20, l=20, b=130),
            xaxis=dict(tickangle=-35, automargin=True),
            yaxis=dict(automargin=True),
        )
    st.plotly_chart(fig, width="stretch")


def _is_restricted_individual_profile() -> bool:
    role = str(st.session_state.get("user_role", "participante")).strip().lower()
    return role in {"participante", "inativo"}


def _get_logged_user_name() -> str:
    return str(st.session_state.get("user_nome", "")).strip()


def _get_logged_user_id() -> Optional[int]:
    raw = st.session_state.get("user_id")
    try:
        return int(raw) if raw is not None and str(raw).strip() != "" else None
    except (TypeError, ValueError):
        return None

def _get_participantes_temporada(temporada: Optional[str] = None) -> pd.DataFrame:
    participantes_df = get_participantes_temporada_df(temporada)
    if participantes_df.empty:
        return participantes_df
    participantes_df = _normalizar_ids(participantes_df, "id")
    if participantes_df.empty:
        return participantes_df
    if 'perfil' in participantes_df.columns:
        participantes_df = participantes_df[participantes_df['perfil'].str.lower() != 'master']
    else:
        participantes_df = participantes_df[participantes_df['nome'] != 'Master']
    return participantes_df


def _get_log_apostas_df(
    conn,
    temporada: Optional[str],
    participantes_ids: list[int],
    participantes_nomes: list[str],
    campos: list[str]
) -> pd.DataFrame:
    """Busca log_apostas via cursor psycopg3 (compatível com dict_row)."""
    cols = get_table_columns(conn, 'log_apostas')
    if not cols:
        return pd.DataFrame()

    conditions = ["tipo_aposta = 0"]
    params: list = []

    if temporada and 'temporada' in cols:
        conditions.append("temporada = %s")
        params.append(temporada)

    id_placeholders = ','.join(['%s'] * len(participantes_ids)) if participantes_ids else ''
    nome_placeholders = ','.join(['%s'] * len(participantes_nomes)) if participantes_nomes else ''

    if participantes_ids and 'usuario_id' in cols and participantes_nomes and 'apostador' in cols:
        conditions.append(f"(usuario_id IN ({id_placeholders}) OR apostador IN ({nome_placeholders}))")
        params.extend(participantes_ids)
        params.extend(participantes_nomes)
    elif participantes_ids and 'usuario_id' in cols:
        conditions.append(f"usuario_id IN ({id_placeholders})")
        params.extend(participantes_ids)
    elif participantes_nomes and 'apostador' in cols:
        conditions.append(f"apostador IN ({nome_placeholders})")
        params.extend(participantes_nomes)

    if not conditions:
        return pd.DataFrame()

    # Mapeia alias de campos para nomes reais (ex: 'apostador AS participante')
    select_cols = ', '.join(campos)
    where_sql = ' AND '.join(conditions)
    query = f"SELECT {select_cols} FROM log_apostas WHERE {where_sql}"

    cur = conn.cursor()
    cur.execute(query, tuple(params))
    rows = cur.fetchall() or []
    cur.close()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def get_apostas_por_piloto(temporada: Optional[str] = None, participantes_df: Optional[pd.DataFrame] = None):
    """
    Agrupa apostas por participante e piloto para análise da distribuição de apostas.
    Retorna DataFrame: participante | piloto | total_apostas
    """
    try:
        if participantes_df is None:
            participantes_df = _get_participantes_temporada(temporada)
        if participantes_df.empty:
            return pd.DataFrame()
        participantes_df = _normalizar_ids(participantes_df, "id")
        if participantes_df.empty:
            return pd.DataFrame()

        participantes_ids = _extrair_ids_validos(participantes_df, "id")
        participantes_nomes = participantes_df['nome'].astype(str).tolist()
        if not participantes_ids:
            return pd.DataFrame()

        with db_connect() as conn:
            cols = get_table_columns(conn, 'apostas')
            placeholders = ','.join(['%s'] * len(participantes_ids))
            if temporada and 'temporada' in cols:
                query = (
                    "SELECT a.usuario_id AS user_id, u.nome AS participante, a.pilotos "
                    "FROM apostas a "
                    "JOIN usuarios u ON a.usuario_id = u.id "
                    f"WHERE a.usuario_id IN ({placeholders}) AND a.temporada = %s"
                )
                params = (*participantes_ids, temporada)
            else:
                query = (
                    "SELECT a.usuario_id AS user_id, u.nome AS participante, a.pilotos "
                    "FROM apostas a "
                    "JOIN usuarios u ON a.usuario_id = u.id "
                    f"WHERE a.usuario_id IN ({placeholders})"
                )
                params = tuple(participantes_ids)
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall() or []
            cur.close()
            df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
            if df.empty:
                df = _get_log_apostas_df(
                    conn,
                    temporada,
                    participantes_ids,
                    participantes_nomes,
                    ['usuario_id AS user_id', 'apostador AS participante', 'pilotos']
                )
            if not df.empty and 'pilotos' in df.columns:
                df['piloto'] = df['pilotos'].str.split(',')
                df = df.explode('piloto')
                df = df.groupby(['user_id', 'participante', 'piloto'], dropna=False).size().reset_index(name='total_apostas')
            else:
                df = pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao buscar apostas por piloto: {str(e)}")
        df = pd.DataFrame()
    return df

def get_distribuicao_piloto_11(temporada: Optional[str] = None, participantes_df: Optional[pd.DataFrame] = None):
    """
    Distribuição de apostas para o 11º colocado por participante.
    Retorna DataFrame: participante | piloto_11
    """
    try:
        if participantes_df is None:
            participantes_df = _get_participantes_temporada(temporada)
        if participantes_df.empty:
            return pd.DataFrame()
        participantes_df = _normalizar_ids(participantes_df, "id")
        if participantes_df.empty:
            return pd.DataFrame()

        participantes_ids = _extrair_ids_validos(participantes_df, "id")
        participantes_nomes = participantes_df['nome'].astype(str).tolist()
        if not participantes_ids:
            return pd.DataFrame()

        with db_connect() as conn:
            cols = get_table_columns(conn, 'apostas')
            placeholders = ','.join(['%s'] * len(participantes_ids))
            if temporada and 'temporada' in cols:
                query = (
                    "SELECT a.usuario_id AS user_id, u.nome AS participante, a.piloto_11 AS piloto_11 "
                    "FROM apostas a "
                    "JOIN usuarios u ON a.usuario_id = u.id "
                    f"WHERE a.usuario_id IN ({placeholders}) AND a.temporada = %s "
                    "AND a.piloto_11 IS NOT NULL AND a.piloto_11 != ''"
                )
                params = (*participantes_ids, temporada)
            else:
                query = (
                    "SELECT a.usuario_id AS user_id, u.nome AS participante, a.piloto_11 AS piloto_11 "
                    "FROM apostas a "
                    "JOIN usuarios u ON a.usuario_id = u.id "
                    f"WHERE a.usuario_id IN ({placeholders}) "
                    "AND a.piloto_11 IS NOT NULL AND a.piloto_11 != ''"
                )
                params = tuple(participantes_ids)
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall() or []
            cur.close()
            df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
            if df.empty:
                df = _get_log_apostas_df(
                    conn,
                    temporada,
                    participantes_ids,
                    participantes_nomes,
                    ['usuario_id AS user_id', 'apostador AS participante', 'piloto_11']
                )
    except Exception as e:
        st.error(f"Erro ao buscar distribuição do 11º colocado: {str(e)}")
        df = pd.DataFrame()
    return df

def main():
    render_page_header(st, "Análise Detalhada das Apostas")

    if not usuarios_status_historico_disponivel():
        st.warning(
            "⚠️ Aviso técnico: histórico de status de usuários indisponível. "
            "As análises por temporada podem considerar o status atual de participantes."
        )

    # Seletor de temporada para diagnósticos
    season_options = get_season_options()
    if not season_options:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    season_default_idx = get_default_season_index(season_options)
    season = st.selectbox("Temporada", season_options, index=season_default_idx, key="analysis_season")
    participantes_df = _get_participantes_temporada(season)

    apostas_pilotos = get_apostas_por_piloto(season, participantes_df)
    df_11 = get_distribuicao_piloto_11(season, participantes_df)

    participante_only_mode = _is_restricted_individual_profile()
    participante_logado = _get_logged_user_name()
    participante_logado_id = _get_logged_user_id()

    if participante_only_mode and not participante_logado and participante_logado_id is None:
        st.warning("Não foi possível identificar o usuário logado para limitar as análises individuais.")
        return

    def _apply_participante_scope(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        mask = pd.Series(False, index=df.index)
        if participante_logado_id is not None and 'user_id' in df.columns:
            ids = pd.to_numeric(df['user_id'], errors='coerce')
            mask = mask | (ids == participante_logado_id)
        if participante_logado and 'participante' in df.columns:
            mask = mask | (df['participante'].astype(str).str.strip() == participante_logado)
        return df[mask].copy()

    if participante_only_mode and (participante_logado or participante_logado_id is not None):
        apostas_pilotos = _apply_participante_scope(apostas_pilotos)
        df_11 = _apply_participante_scope(df_11)

    if apostas_pilotos.empty and df_11.empty:
        st.info("Ainda não há apostas cadastradas para análise.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Distribuição por Piloto (Individual)",
        "Apostas no 11º (Individual)",
        "Consolidado Pilotos",
        "Consolidado 11º",
        "Diagnóstico Regras/Provas"
    ])

    with tab1:
        st.subheader("Distribuição por Piloto - Individual")
        if apostas_pilotos.empty:
            st.info("Sem dados para análise por piloto.")
        else:
            participantes = sorted(apostas_pilotos['participante'].unique().tolist())
            if participante_only_mode and participante_logado:
                participante_sel = participante_logado
                st.caption(f"Exibindo estatísticas individuais de: {participante_sel}")
            else:
                participante_sel = st.selectbox(
                    "Participante",
                    participantes,
                    key=f"analysis_piloto_participante_{season}"
                )
            df_filtrado = apostas_pilotos[apostas_pilotos['participante'] == participante_sel]
            _plot_colunas(
                df_filtrado,
                x_col='piloto',
                y_col='total_apostas',
                title=f"Apostas de {participante_sel}"
            )

    with tab2:
        st.subheader("Distribuição do 11º Colocado - Individual")
        if not df_11.empty:
            participantes_11 = sorted(df_11['participante'].unique().tolist())
            if participante_only_mode and participante_logado:
                participante_11_sel = participante_logado
                st.caption(f"Exibindo estatísticas individuais (11º) de: {participante_11_sel}")
            else:
                participante_11_sel = st.selectbox(
                    "Participante (11º)",
                    participantes_11,
                    key=f"analysis_11_participante_{season}"
                )
            df_part = df_11[df_11['participante'] == participante_11_sel]
            contagem = df_part['piloto_11'].value_counts().reset_index()
            contagem.columns = ['Piloto', 'Total']
            _plot_colunas(
                contagem,
                x_col='Piloto',
                y_col='Total',
                title=f"Pilotos apostados como 11º por {participante_11_sel}"
            )
            st.dataframe(
                contagem,
                width="stretch",
                hide_index=True,
                height=_table_height(len(contagem)),
                column_config={
                    "Piloto": st.column_config.TextColumn("Piloto", width="medium"),
                    "Total": st.column_config.NumberColumn("Total", format="%d", width="small"),
                },
            )
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")

    with tab3:
        st.subheader("Consolidado de Apostas por Piloto")
        if not apostas_pilotos.empty:
            consolidado_pilotos = apostas_pilotos.groupby('piloto')['total_apostas'].sum().reset_index()
            _plot_colunas(
                consolidado_pilotos,
                x_col='piloto',
                y_col='total_apostas',
                title="Distribuição Geral de Apostas por Piloto"
            )
            st.dataframe(
                consolidado_pilotos,
                width="stretch",
                hide_index=True,
                height=_table_height(len(consolidado_pilotos)),
                column_config={
                    "piloto": st.column_config.TextColumn("Piloto", width="medium"),
                    "total_apostas": st.column_config.NumberColumn("Total de apostas", format="%d", width="small"),
                },
            )
        else:
            st.info("Nenhuma aposta registrada para pilotos.")

    with tab4:
        st.subheader("Consolidado do 11º Colocado")
        if not df_11.empty:
            consolidado_11 = df_11['piloto_11'].value_counts().reset_index()
            consolidado_11.columns = ['Piloto', 'Total']
            _plot_colunas(
                consolidado_11,
                x_col='Piloto',
                y_col='Total',
                title="Distribuição Geral de Pilotos apostados como 11º"
            )
            st.dataframe(
                consolidado_11,
                width="stretch",
                hide_index=True,
                height=_table_height(len(consolidado_11)),
                column_config={
                    "Piloto": st.column_config.TextColumn("Piloto", width="medium"),
                    "Total": st.column_config.NumberColumn("Total", format="%d", width="small"),
                },
            )
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")

    with tab5:
        st.subheader("Diagnóstico de Tipos de Prova e Regras Aplicadas")
        provas_df = _normalizar_ids(get_provas_df(season), "id")
        resultados_df = _normalizar_ids(get_resultados_df(season), "prova_id")
        apostas_df = _normalizar_ids(get_apostas_df(season), "prova_id")
        if not apostas_df.empty and 'temporada' in apostas_df.columns:
            apostas_df = apostas_df[apostas_df['temporada'] == season]
        if provas_df.empty:
            st.info("Nenhuma prova cadastrada para a temporada selecionada.")
        else:
            # Resolver tipo Sprint/Normal por linha
            tipos_resolvidos = []
            for _, pr in provas_df.iterrows():
                tipo = pr['tipo'] if 'tipo' in provas_df.columns and pd.notna(pr.get('tipo')) else None
                nome = pr.get('nome', '')
                is_sprint = (str(tipo).strip().lower() == 'sprint') or ('sprint' in str(nome).lower())
                tipos_resolvidos.append('Sprint' if is_sprint else 'Normal')
            provas_df = provas_df.copy()
            provas_df['tipo_resolvido'] = tipos_resolvidos

            linhas = []
            for _, pr in provas_df.iterrows():
                rid = pr['id']
                tipo = pr['tipo_resolvido']
                regra = get_regras_aplicaveis(str(season), tipo)
                pts = regra.get('pontos_posicoes', [])
                linhas.append({
                    'prova_id': rid,
                    'nome': pr.get('nome', ''),
                    'data': pr.get('data', ''),
                    'tipo_resolvido': tipo,
                    'regra_nome': regra.get('nome_regra', ''),
                    'quantidade_fichas': regra.get('quantidade_fichas', ''),
                    'min_pilotos': regra.get('qtd_minima_pilotos', regra.get('min_pilotos', '')),
                    'fichas_por_piloto': regra.get('fichas_por_piloto', ''),
                    'pontos_dobrada': regra.get('pontos_dobrada', False),
                    'pontos_posicoes_len': len(pts),
                    'pontos_posicoes_preview': ','.join(map(str, pts[:10])) if pts else '',
                    'tem_resultado': rid in resultados_df['prova_id'].values if not resultados_df.empty else False,
                    'qtd_apostas': int(apostas_df[apostas_df['prova_id'] == rid].shape[0]) if not apostas_df.empty else 0
                })
            diag = pd.DataFrame(linhas)
            st.dataframe(
                diag,
                width="stretch",
                hide_index=True,
                height=_table_height(len(diag), max_height=640),
                column_config={
                    "prova_id": st.column_config.NumberColumn("ID", format="%d", width="small"),
                    "nome": st.column_config.TextColumn("Prova", width="large"),
                    "data": st.column_config.TextColumn("Data", width="small"),
                    "tipo_resolvido": st.column_config.TextColumn("Tipo", width="small"),
                    "regra_nome": st.column_config.TextColumn("Regra", width="medium"),
                    "quantidade_fichas": st.column_config.NumberColumn("Fichas", width="small"),
                    "min_pilotos": st.column_config.NumberColumn("Min. Pilotos", width="small"),
                    "fichas_por_piloto": st.column_config.NumberColumn("Fichas/Piloto", width="small"),
                    "pontos_dobrada": st.column_config.CheckboxColumn("Dobrada", width="small"),
                    "pontos_posicoes_len": st.column_config.NumberColumn("Qtd Pontos", width="small"),
                    "pontos_posicoes_preview": st.column_config.TextColumn("Preview Pontos", width="large"),
                    "tem_resultado": st.column_config.CheckboxColumn("Tem Resultado", width="small"),
                    "qtd_apostas": st.column_config.NumberColumn("Qtd Apostas", format="%d", width="small"),
                },
            )
            st.caption("Tipo resolvido usa coluna 'tipo' ou contém 'Sprint' no nome. Pontos e parâmetros vêm das regras da temporada.")

if __name__ == "__main__":
    main()
