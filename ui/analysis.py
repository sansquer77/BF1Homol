import streamlit as st
import pandas as pd
import plotly.express as px
from db.db_utils import (
    db_connect,
    get_provas_df,
    get_apostas_df,
    get_resultados_df,
    get_participantes_temporada_df
)
from db.backup_utils import list_temporadas
from services.rules_service import get_regras_aplicaveis

def _get_participantes_temporada(temporada: str | None = None) -> pd.DataFrame:
    participantes_df = get_participantes_temporada_df(temporada)
    if participantes_df.empty:
        return participantes_df
    if 'perfil' in participantes_df.columns:
        participantes_df = participantes_df[participantes_df['perfil'].str.lower() != 'master']
    else:
        participantes_df = participantes_df[participantes_df['nome'] != 'Master']
    return participantes_df


def _get_log_apostas_df(
    conn,
    temporada: str | None,
    participantes_ids: list[int],
    participantes_nomes: list[str],
    campos: list[str]
) -> pd.DataFrame:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info('log_apostas')")
    cols = [r[1] for r in cursor.fetchall()]
    if not cols:
        return pd.DataFrame()

    conditions = ["tipo_aposta = 0"]
    params: list = []

    if temporada and 'temporada' in cols:
        conditions.append("temporada = ?")
        params.append(temporada)

    id_placeholders = ','.join(['?'] * len(participantes_ids)) if participantes_ids else ''
    nome_placeholders = ','.join(['?'] * len(participantes_nomes)) if participantes_nomes else ''

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

    select_cols = ', '.join(campos)
    where_sql = ' AND '.join(conditions)
    query = f"SELECT {select_cols} FROM log_apostas WHERE {where_sql}"
    return pd.read_sql(query, conn, params=tuple(params))


def get_apostas_por_piloto(temporada: str | None = None, participantes_df: pd.DataFrame | None = None):
    """
    Agrupa apostas por participante e piloto para análise da distribuição de apostas.
    Retorna DataFrame: participante | piloto | total_apostas
    """
    try:
        if participantes_df is None:
            participantes_df = _get_participantes_temporada(temporada)
        if participantes_df.empty:
            return pd.DataFrame()
        participantes_ids = participantes_df['id'].astype(int).tolist()
        participantes_nomes = participantes_df['nome'].astype(str).tolist()

        with db_connect() as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info('apostas')")
            cols = [r[1] for r in c.fetchall()]
            placeholders = ','.join(['?'] * len(participantes_ids))
            if temporada and 'temporada' in cols:
                query = '''
                    SELECT u.nome AS participante, a.pilotos
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    WHERE a.usuario_id IN ({}) AND a.temporada = ?
                '''
                df = pd.read_sql(query.format(placeholders), conn, params=(*participantes_ids, temporada))
            else:
                query = '''
                    SELECT u.nome AS participante, a.pilotos
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    WHERE a.usuario_id IN ({})
                '''
                df = pd.read_sql(query.format(placeholders), conn, params=tuple(participantes_ids))
            if df.empty:
                df = _get_log_apostas_df(
                    conn,
                    temporada,
                    participantes_ids,
                    participantes_nomes,
                    ['apostador AS participante', 'pilotos']
                )
            if not df.empty and 'pilotos' in df.columns:
                df['piloto'] = df['pilotos'].str.split(',')
                df = df.explode('piloto')
                df = df.groupby(['participante', 'piloto']).size().reset_index(name='total_apostas')
            else:
                df = pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao buscar apostas por piloto: {str(e)}")
        df = pd.DataFrame()
    return df

def get_distribuicao_piloto_11(temporada: str | None = None, participantes_df: pd.DataFrame | None = None):
    """
    Distribuição de apostas para o 11º colocado por participante.
    Retorna DataFrame: participante | piloto_11
    """
    try:
        if participantes_df is None:
            participantes_df = _get_participantes_temporada(temporada)
        if participantes_df.empty:
            return pd.DataFrame()
        participantes_ids = participantes_df['id'].astype(int).tolist()
        participantes_nomes = participantes_df['nome'].astype(str).tolist()

        with db_connect() as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info('apostas')")
            cols = [r[1] for r in c.fetchall()]
            placeholders = ','.join(['?'] * len(participantes_ids))
            if temporada and 'temporada' in cols:
                query = '''
                    SELECT u.nome AS participante, a.piloto_11 AS piloto_11
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    WHERE a.usuario_id IN ({}) AND a.temporada = ?
                    AND a.piloto_11 IS NOT NULL AND a.piloto_11 != ''
                '''
                df = pd.read_sql(query.format(placeholders), conn, params=(*participantes_ids, temporada))
            else:
                query = '''
                    SELECT u.nome AS participante, a.piloto_11 AS piloto_11
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    WHERE a.usuario_id IN ({})
                    AND a.piloto_11 IS NOT NULL AND a.piloto_11 != ''
                '''
                df = pd.read_sql(query.format(placeholders), conn, params=tuple(participantes_ids))
            if df.empty:
                df = _get_log_apostas_df(
                    conn,
                    temporada,
                    participantes_ids,
                    participantes_nomes,
                    ['apostador AS participante', 'piloto_11']
                )
    except Exception as e:
        st.error(f"Erro ao buscar distribuição do 11º colocado: {str(e)}")
        df = pd.DataFrame()
    return df

def main():
    st.title("📊 Análise Detalhada das Apostas")

    # Seletor de temporada para diagnósticos
    try:
        season_options = list_temporadas() or []
    except Exception:
        season_options = []
    if not season_options:
        import datetime as dt
        season_options = [str(dt.datetime.now().year)]
    season = st.selectbox("Temporada", season_options, key="analysis_season")
    participantes_df = _get_participantes_temporada(season)

    apostas_pilotos = get_apostas_por_piloto(season, participantes_df)
    df_11 = get_distribuicao_piloto_11(season, participantes_df)

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
            participantes = apostas_pilotos['participante'].unique()
            for participante in participantes:
                df_filtrado = apostas_pilotos[apostas_pilotos['participante'] == participante]
                fig = px.pie(
                    df_filtrado, names='piloto', values='total_apostas',
                    title=f"Apostas de {participante}"
                )
                st.plotly_chart(fig, width="stretch")

    with tab2:
        st.subheader("Distribuição do 11º Colocado - Individual")
        if not df_11.empty:
            participantes_11 = df_11['participante'].unique()
            for participante in participantes_11:
                df_part = df_11[df_11['participante'] == participante]
                contagem = df_part['piloto_11'].value_counts().reset_index()
                contagem.columns = ['Piloto', 'Total']
                fig = px.pie(
                    contagem, names='Piloto', values='Total',
                    title=f"Pilotos apostados como 11º por {participante}"
                )
                st.plotly_chart(fig, width="stretch")
                st.dataframe(contagem)
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")

    with tab3:
        st.subheader("Consolidado de Apostas por Piloto")
        if not apostas_pilotos.empty:
            consolidado_pilotos = apostas_pilotos.groupby('piloto')['total_apostas'].sum().reset_index()
            fig = px.pie(
                consolidado_pilotos, names='piloto', values='total_apostas',
                title="Distribuição Geral de Apostas por Piloto"
            )
            st.plotly_chart(fig, width="stretch")
            st.dataframe(consolidado_pilotos, width="stretch")
        else:
            st.info("Nenhuma aposta registrada para pilotos.")

    with tab4:
        st.subheader("Consolidado do 11º Colocado")
        if not df_11.empty:
            consolidado_11 = df_11['piloto_11'].value_counts().reset_index()
            consolidado_11.columns = ['Piloto', 'Total']
            fig = px.pie(
                consolidado_11, names='Piloto', values='Total',
                title="Distribuição Geral de Pilotos apostados como 11º"
            )
            st.plotly_chart(fig, width="stretch")
            st.dataframe(consolidado_11)
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")

    with tab5:
        st.subheader("Diagnóstico de Tipos de Prova e Regras Aplicadas")
        provas_df = get_provas_df(season)
        resultados_df = get_resultados_df(season)
        apostas_df = get_apostas_df(season)
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
            st.dataframe(diag, width="stretch")
            st.caption("Tipo resolvido usa coluna 'tipo' ou contém 'Sprint' no nome. Pontos e parâmetros vêm das regras da temporada.")

if __name__ == "__main__":
    main()
