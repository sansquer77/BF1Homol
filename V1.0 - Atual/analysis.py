import streamlit as st
import pandas as pd
import plotly.express as px
from db_utils import db_connect

def get_apostas_por_piloto():
    conn = db_connect()
    query = '''
    SELECT u.nome AS participante, a.pilotos 
    FROM apostas a
    JOIN usuarios u ON a.usuario_id = u.id
    '''
    try:
        df = pd.read_sql(query, conn)
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

def get_distribuicao_piloto_11():
    conn = db_connect()
    query = '''
    SELECT u.nome AS participante, a.piloto_11 AS piloto_11
    FROM apostas a
    JOIN usuarios u ON a.usuario_id = u.id
    WHERE a.piloto_11 IS NOT NULL AND a.piloto_11 != ''
    '''
    try:
        df = pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro ao buscar distribuição do 11º colocado: {str(e)}")
        df = pd.DataFrame()
    return df

def main():
    st.title("Análise Detalhada das Apostas")
    
    apostas_pilotos = get_apostas_por_piloto()
    df_11 = get_distribuicao_piloto_11()  # Corrigido: usa a nova função
    
    if apostas_pilotos.empty and df_11.empty:
        st.info("Sem apostas até o momento.")
        return
    
    # Tabs para organização
    tab1, tab2, tab3, tab4 = st.tabs([
        "Distribuição por Piloto (Individual)",
        "Apostas no 11º (Individual)",
        "Consolidado Pilotos",
        "Consolidado 11º"
    ])
    
    with tab1:
        st.subheader("Distribuição por Piloto - Individual")
        participantes = apostas_pilotos['participante'].unique()
        for participante in participantes:
            df_filtrado = apostas_pilotos[apostas_pilotos['participante'] == participante]
            fig = px.pie(df_filtrado, names='piloto', values='total_apostas', 
                        title=f"Apostas de {participante}")
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:  # CORREÇÃO DE INDENTAÇÃO
        st.subheader("Distribuição de Pilotos Apostados no 11º Colocado - Individual")
        if not df_11.empty:
            participantes_11 = df_11['participante'].unique()
            for participante in participantes_11:
                df_part = df_11[df_11['participante'] == participante]
                contagem = df_part['piloto_11'].value_counts().reset_index()
                contagem.columns = ['Piloto', 'Total']
                fig = px.pie(contagem, names='Piloto', values='Total',
                            title=f"Pilotos apostados como 11º por {participante}")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(contagem)
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")
    
    with tab3:
        st.subheader("Consolidado de Apostas por Piloto")
        consolidado_pilotos = apostas_pilotos.groupby('piloto')['total_apostas'].sum().reset_index()
        fig = px.pie(consolidado_pilotos, names='piloto', values='total_apostas',
                    title="Distribuição Geral de Apostas por Piloto")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(consolidado_pilotos, use_container_width=True)
    
    with tab4:  # CORREÇÃO DE INDENTAÇÃO
        st.subheader("Consolidado de Pilotos Apostados no 11º Colocado")
        if not df_11.empty:
            consolidado_11 = df_11['piloto_11'].value_counts().reset_index()
            consolidado_11.columns = ['Piloto', 'Total']
            fig = px.pie(consolidado_11, names='Piloto', values='Total',
                        title="Distribuição Geral de Pilotos apostados como 11º")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(consolidado_11)
        else:
            st.info("Nenhuma aposta registrada para o 11º colocado.")
