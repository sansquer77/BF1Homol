import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib.image as mpimg
import datetime as dt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

from db.db_utils import db_connect, get_usuarios_df, get_provas_df, get_apostas_df, get_resultados_df
from db.backup_utils import list_temporadas
from services.championship_service import get_final_results, get_championship_bet
from services.bets_service import calcular_pontuacao_lote

def formatar_brasileiro(valor):
    try:
        return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    except:
        return valor

def gerar_imagem_tabela_ajustada(df, colunas):
    max_larguras = []
    for col in colunas:
        max_len = df[col].astype(str).map(len).max()
        max_len = max(max_len, len(col))
        max_larguras.append(max_len)
    escala_largura = 0.3
    proporcional_largura = [l * escala_largura for l in max_larguras]
    largura_figura = sum(proporcional_largura)
    altura_figura = len(df) * 0.4 + 1.5

    fig, ax = plt.subplots(figsize=(largura_figura, altura_figura))
    ax.axis('off')

    # Logo pequeno no canto superior esquerdo
    try:
        logo = mpimg.imread("BF1.jpg")
        logo_img = OffsetImage(logo, zoom=0.15)
        ab = AnnotationBbox(logo_img, (0, 1), xycoords='axes fraction', frameon=False, box_alignment=(0, 1), pad=0.03)
        ax.add_artist(ab)
    except Exception:
        pass

    tabela = ax.table(
        cellText=df[colunas].values,
        colLabels=colunas,
        cellLoc='center',
        loc='center'
    )
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(10)
    tabela.scale(1.2, 1.2)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buffer.seek(0)
    return buffer

def gerar_imagem_prova(df_cruzada, prova_selecionada):
    if prova_selecionada not in df_cruzada.index:
        return None
    dados_prova = df_cruzada.loc[prova_selecionada]
    dados_ordenados = dados_prova.sort_values(ascending=False)
    df_prova = pd.DataFrame({prova_selecionada: dados_ordenados})
    df_prova[prova_selecionada] = df_prova[prova_selecionada].apply(
        lambda x: f'{x:,.2f}'.replace(',', 'v').replace('.', ',').replace('v', '.'))

    linhas = len(df_prova)
    fig, ax = plt.subplots(figsize=(6, linhas * 0.5 + 1.5))
    ax.axis('off')
    try:
        logo = mpimg.imread("BF1.jpg")
        logo_img = OffsetImage(logo, zoom=0.12)
        ab = AnnotationBbox(logo_img, (0, 1), xycoords='axes fraction', frameon=False, box_alignment=(0, 1), pad=0.03)
        ax.add_artist(ab)
    except Exception:
        pass
    table = ax.table(
        cellText=df_prova.values,
        rowLabels=df_prova.index,
        colLabels=[prova_selecionada],
        cellLoc='center',
        loc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 1.2)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buffer.seek(0)
    return buffer

def destacar_heatmap(df, resultados_df, provas_ids_ordenados):
    def colorir_prova_heatmap(row):
        estilos = [''] * len(row)
        prova_nome = row.name
        prova_idx = [i for i, nome in enumerate(df.index) if nome == prova_nome]
        if not prova_idx:
            return estilos
        prova_id = provas_ids_ordenados[prova_idx[0]]
        if prova_id not in resultados_df['prova_id'].values:
            return estilos
        valores = row.astype(str).str.replace('.', '').str.replace(',', '.').astype(float)
        min_val = valores.min()
        max_val = valores.max()
        if max_val == min_val:
            norm_vals = np.zeros_like(valores)
        else:
            norm_vals = (valores - min_val) / (max_val - min_val)
        for i, norm_val in enumerate(norm_vals):
            r = int(255 * (1 - norm_val))
            g = int(255 * norm_val)
            b = 0
            estilos[i] = f'background-color: rgb({r},{g},{b}); font-weight: bold; color: black'
        return estilos
    return df.style.apply(colorir_prova_heatmap, axis=1)

def main():
    col1, col2 = st.columns([1, 16])
    with col1:
        st.image("BF1.jpg", width=75)
    with col2:
        st.title("Classificação Geral do Bolão")

    # Season selector - read from temporadas table
    current_year = dt.datetime.now().year
    current_year_str = str(current_year)
    
    try:
        season_options = list_temporadas() or []
    except Exception:
        season_options = []
    
    # Fallback to fixed options if temporadas table is empty
    if not season_options:
        season_options = ["2025", "2026"]
    
    # Default to current year when present, otherwise first option
    if current_year_str in season_options:
        default_index = season_options.index(current_year_str)
    else:
        default_index = 0
    
    season = st.selectbox("Temporada", season_options, index=default_index, key="classificacao_season")
    st.session_state['temporada'] = season

    usuarios_df = get_usuarios_df()
    provas_df = get_provas_df(season)
    apostas_df = get_apostas_df(season)
    resultados_df = get_resultados_df(season)

    participantes = usuarios_df[(usuarios_df['status'] == 'Ativo') & (usuarios_df['nome'] != 'Master')]
    provas_df = provas_df.sort_values('data')
    perfil_usuario = st.session_state.get("user_role", "usuario").strip().lower()
    tabela_classificacao = []
    tabela_detalhada = []

    for idx, part in participantes.iterrows():
        apostas_part = apostas_df[apostas_df['usuario_id'] == part['id']].sort_values('prova_id')
        pontos_part = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df)
        total = sum([p for p in pontos_part if p is not None])
        tabela_classificacao.append({
            "Participante": part['nome'],
            "usuario_id": part['id'],
            "Pontos Provas": total
        })
        tabela_detalhada.append({
            "Participante": part['nome'],
            "Pontos por Prova": pontos_part
        })

    df_class = pd.DataFrame(tabela_classificacao)
    df_class = df_class.sort_values("Pontos Provas", ascending=False).reset_index(drop=True)
    df_class["Pontos Provas"] = df_class["Pontos Provas"].apply(lambda x: formatar_brasileiro(float(x)))
    df_class['Posição'] = df_class.index + 1
    provas_realizadas = provas_df[provas_df['id'].isin(resultados_df['prova_id'])]
    if len(provas_realizadas) > 1:
        penultima_prova_id = provas_realizadas.iloc[-2]['id']
        provas_ate_penultima = provas_realizadas[provas_realizadas['id'] <= penultima_prova_id]['id'].tolist()
        tabela_anterior = []
        for idx, part in participantes.iterrows():
            apostas_anteriores = apostas_df[
                (apostas_df['usuario_id'] == part['id']) &
                (apostas_df['prova_id'].isin(provas_ate_penultima))
            ].sort_values('prova_id')
            pontos_anteriores = calcular_pontuacao_lote(apostas_anteriores, resultados_df, provas_df)
            total_anteriores = sum([p for p in pontos_anteriores if p is not None])
            tabela_anterior.append({
                "Participante": part['nome'],
                "usuario_id": part['id'],
                "Pontos Provas": total_anteriores
            })

        df_class_anterior = pd.DataFrame(tabela_anterior)
        df_class_anterior = df_class_anterior.sort_values("Pontos Provas", ascending=False).reset_index(drop=True)
        df_class_anterior['Posição Anterior'] = df_class_anterior.index + 1
        df_class = df_class.merge(
            df_class_anterior[['usuario_id', 'Posição Anterior']],
            on='usuario_id',
            how='left'
        )

        def movimento(row):
            if pd.isnull(row['Posição Anterior']):
                return "Novo"
            diff = int(row['Posição Anterior']) - int(row['Posição'])
            if diff > 0:
                return f"Subiu {diff}"
            elif diff < 0:
                return f"Caiu {abs(diff)}"
            else:
                return "Permaneceu"
        df_class['Movimentação'] = df_class.apply(movimento, axis=1)
    else:
        df_class['Movimentação'] = "Novo"

    pontos_float = [float(x.replace('.', '').replace(',', '.')) for x in df_class["Pontos Provas"]]
    diferencas = [0]
    for i in range(1, len(pontos_float)):
        diferencas.append(pontos_float[i-1] - pontos_float[i])
    df_class["Diferença"] = ["-" if i == 0 else formatar_brasileiro(d) for i, d in enumerate(diferencas)]
    colunas_ordem = ["Posição", "Participante", "Pontos Provas", "Diferença", "Movimentação"]
    st.subheader("Classificação Geral - Apenas Provas")
    st.table(df_class[colunas_ordem])

    if perfil_usuario in ['admin', 'master']:
        imagem_buffer = gerar_imagem_tabela_ajustada(df_class, colunas_ordem)
        st.download_button(
            label='Baixar imagem da tabela',
            data=imagem_buffer,
            file_name='classificacao_geral.png',
            mime='image/png'
        )
    resultado_campeonato = get_final_results()
    tabela_classificacao_completa = []
    for idx, part in participantes.iterrows():
        apostas_part = apostas_df[apostas_df['usuario_id'] == part['id']].sort_values('prova_id')
        pontos_part = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df)
        pontos_provas = sum([p for p in pontos_part if p is not None])
        aposta = get_championship_bet(part['id'])
        pontos_campeonato = 0
        acertos = []
        if resultado_campeonato and aposta:
            if resultado_campeonato.get("champion") == aposta.get("champion"):
                pontos_campeonato += 150
                acertos.append("Campeão")
            if resultado_campeonato.get("vice") == aposta.get("vice"):
                pontos_campeonato += 100
                acertos.append("Vice")
            if resultado_campeonato.get("team") == aposta.get("team"):
                pontos_campeonato += 80
                acertos.append("Equipe")
        total_geral = pontos_provas + pontos_campeonato
        tabela_classificacao_completa.append({
            "Participante": part['nome'],
            "Pontos Provas": pontos_provas,
            "Pontos Campeonato": pontos_campeonato,
            "Total Geral": total_geral,
            "Acertos Campeonato": ", ".join(acertos) if acertos else "-"
        })
    df_class_completo = pd.DataFrame(tabela_classificacao_completa)
    df_class_completo = df_class_completo.sort_values("Total Geral", ascending=False).reset_index(drop=True)
    for col in ["Pontos Provas", "Pontos Campeonato", "Total Geral"]:
        df_class_completo[col] = df_class_completo[col].apply(lambda x: formatar_brasileiro(float(x)))
    st.subheader("Classificação Final (Provas + Campeonato)")
    st.table(df_class_completo)

    st.subheader("Pontuação por Prova")
    provas_df_ord = provas_df.sort_values('id')
    provas_nomes = provas_df_ord['nome'].tolist()
    provas_ids_ordenados = provas_df_ord['id'].tolist()
    dados_cruzados = {prova_nome: {} for prova_nome in provas_nomes}
    for part in tabela_detalhada:
        participante = part['Participante']
        pontos_por_prova = {}
        usuario_id = participantes[participantes['nome'] == participante].iloc[0]['id']
        apostas_part = apostas_df[apostas_df['usuario_id'] == usuario_id]
        for _, aposta in apostas_part.iterrows():
            pontos = calcular_pontuacao_lote(pd.DataFrame([aposta]), resultados_df, provas_df)
            if pontos:
                pontos_por_prova[aposta['prova_id']] = pontos[0]
        for prova_id, prova_nome in zip(provas_ids_ordenados, provas_nomes):
            pontos = pontos_por_prova.get(prova_id, 0)
            dados_cruzados[prova_nome][participante] = pontos if pontos is not None else 0
    df_cruzada = pd.DataFrame(dados_cruzados).T
    df_cruzada = df_cruzada.reindex(
        columns=[p['nome'] for _, p in participantes.iterrows()],
        fill_value=0
    )
    df_formatado = df_cruzada.applymap(lambda x: formatar_brasileiro(float(x)))
    df_styled = destacar_heatmap(df_formatado, resultados_df, provas_ids_ordenados)
    st.dataframe(df_styled)

    st.subheader("Imagem da classificação de uma prova específica")
    prova_selecionada = st.selectbox(
        "Selecione a prova para gerar imagem da classificação:",
        options=df_cruzada.index.tolist()
    )
    if perfil_usuario in ['admin', 'master']:
        if st.button("Gerar imagem da prova selecionada"):
            imagem_buffer_prova = gerar_imagem_prova(df_cruzada, prova_selecionada)
            if imagem_buffer_prova:
                st.download_button(
                    label=f"Baixar imagem da classificação da prova {prova_selecionada}",
                    data=imagem_buffer_prova,
                    file_name=f'classificacao_{prova_selecionada}.png',
                    mime='image/png'
                )
            else:
                st.warning("Prova selecionada não contém dados para gerar imagem.")

    st.subheader("Evolução da Pontuação Acumulada")
    provas_com_resultado_ids = resultados_df['prova_id'].unique()
    provas_com_resultado_nomes = provas_df[provas_df['id'].isin(provas_com_resultado_ids)].sort_values('id')['nome'].tolist()
    df_grafico = df_cruzada.loc[df_cruzada.index.isin(provas_com_resultado_nomes)]
    df_grafico = df_grafico.reindex(provas_com_resultado_nomes)
    def texto_para_float(x):
        if isinstance(x, float):
            return x
        return float(str(x).replace('.', '').replace(',', '.'))
    df_grafico_float = df_grafico.applymap(texto_para_float)
    if not df_grafico_float.empty:
        fig = go.Figure()
        for participante in df_grafico_float.columns:
            pontos_acumulados = df_grafico_float[participante].cumsum()
            fig.add_trace(go.Scatter(
                x=df_grafico_float.index.tolist(),
                y=pontos_acumulados,
                mode='lines+markers',
                name=participante
            ))
        fig.update_layout(
            title="Evolução da Pontuação Acumulada",
            xaxis_title="Prova",
            yaxis_title="Pontuação Acumulada",
            xaxis_tickangle=-45,
            margin=dict(l=40, r=20, t=60, b=80),
            plot_bgcolor='rgba(240,240,255,0.9)',
            yaxis=dict(tickformat=',.0f')
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para exibir o gráfico de evolução.")

    st.subheader("Classificação de Cada Participante ao Longo do Campeonato")
    with db_connect() as conn:
        # Filter positions by selected season
        query = 'SELECT * FROM posicoes_participantes WHERE temporada = ? OR temporada IS NULL'
        df_posicoes = pd.read_sql(query, conn, params=(season,))
    fig_all = go.Figure()
    for part in participantes['nome']:
        usuario_id = participantes[participantes['nome'] == part].iloc[0]['id']
        posicoes_part = df_posicoes[df_posicoes['usuario_id'] == usuario_id].sort_values('prova_id')
        if not posicoes_part.empty:
            fig_all.add_trace(go.Scatter(
                x=[provas_df[provas_df['id'] == pid]['nome'].values[0] for pid in posicoes_part['prova_id']],
                y=posicoes_part['posicao'],
                mode='lines+markers',
                name=part
            ))
    fig_all.update_yaxes(autorange="reversed")
    fig_all.update_layout(
        xaxis_title="Prova",
        yaxis_title="Posição",
        legend_title="Participante"
    )
    st.plotly_chart(fig_all, use_container_width=True)

if __name__ == "__main__":
    main()
