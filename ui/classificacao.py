import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib.image as mpimg
import datetime as dt
import ast
from zoneinfo import ZoneInfo
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from db.db_utils import db_connect, get_usuarios_df, get_provas_df, get_apostas_df, get_resultados_df
from db.backup_utils import list_temporadas
from services.championship_service import get_final_results, get_championship_bet
from services.rules_service import get_regras_aplicaveis
from services.bets_service import calcular_pontuacao_lote, atualizar_classificacoes_todas_as_provas, _parse_datetime_sp

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

    current_year = dt.datetime.now().year
    current_year_str = str(current_year)
    
    try:
        season_options = list_temporadas() or []
    except Exception:
        season_options = []
    
    if not season_options:
        season_options = ["2025", "2026"]
    
    if current_year_str in season_options:
        default_index = season_options.index(current_year_str)
    else:
        default_index = 0
    
    season = st.selectbox("Temporada", season_options, index=default_index, key="classificacao_season")
    st.session_state['temporada'] = season

    try:
        atualizar_classificacoes_todas_as_provas(temporada=season)
    except Exception as e:
        st.warning(f"⚠️ Erro ao atualizar classificações: {e}")

    usuarios_df = get_usuarios_df()
    provas_df = get_provas_df(season)
    apostas_df = get_apostas_df(season)
    resultados_df = get_resultados_df(season)

    participantes = usuarios_df[(usuarios_df['status'] == 'Ativo') & (usuarios_df['nome'] != 'Master')]
    provas_df = provas_df.sort_values('data')
    perfil_usuario = st.session_state.get("user_role", "usuario").strip().lower()
    
    resultado_campeonato = get_final_results(season)
    
    tabela_classificacao = []
    tabela_detalhada = []

    # Carregar regras da temporada selecionada para bônus de campeonato
    regras_temporada = get_regras_aplicaveis(str(season), "Normal")
    pontos_campeao = regras_temporada.get('pontos_campeao', 150)
    pontos_vice = regras_temporada.get('pontos_vice', 100)
    pontos_equipe = regras_temporada.get('pontos_equipe', 80)

    # Pré-calcular acertos de 11º e apostas no prazo
    acertos_11_por_usuario = {}
    apostas_no_prazo_por_usuario = {}
    apostas_latest = apostas_df.copy()
    if not apostas_latest.empty:
        if 'data_envio' in apostas_latest.columns:
            apostas_latest['__envio_dt'] = pd.to_datetime(apostas_latest['data_envio'], errors='coerce')
            apostas_latest = apostas_latest.sort_values('__envio_dt')
        apostas_latest = apostas_latest.drop_duplicates(subset=['usuario_id', 'prova_id'], keep='last')

    if not resultados_df.empty and not apostas_latest.empty:
        res_11 = []
        for _, r in resultados_df.iterrows():
            try:
                posicoes = ast.literal_eval(r['posicoes'])
                piloto_11_real = str(posicoes.get(11, '')).strip()
            except Exception:
                piloto_11_real = ''
            if piloto_11_real:
                res_11.append({'prova_id': r['prova_id'], 'piloto_11_real': piloto_11_real})
        if res_11:
            res_11_df = pd.DataFrame(res_11)
            merged_11 = apostas_latest.merge(res_11_df, on='prova_id', how='inner')
            merged_11['acerto_11'] = merged_11.apply(
                lambda row: str(row.get('piloto_11', '')).strip() == str(row.get('piloto_11_real', '')).strip(),
                axis=1
            )
            acertos_11_por_usuario = merged_11.groupby('usuario_id')['acerto_11'].sum().to_dict()

    if not apostas_latest.empty and not provas_df.empty:
        provas_map = provas_df.set_index('id').to_dict('index')
        for _, ap in apostas_latest.iterrows():
            prova = provas_map.get(ap['prova_id'])
            if not prova:
                continue
            data_str = prova.get('data')
            hora_str = prova.get('horario_prova', '00:00') or '00:00'
            if not data_str:
                continue
            try:
                cutoff = _parse_datetime_sp(str(data_str), str(hora_str))
                envio = pd.to_datetime(ap.get('data_envio'), errors='coerce')
                if pd.isna(envio):
                    continue
                envio_dt = envio.to_pydatetime()
                if envio_dt.tzinfo is None:
                    envio_dt = envio_dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                if envio_dt.astimezone(ZoneInfo("UTC")) <= cutoff.astimezone(ZoneInfo("UTC")):
                    uid = int(ap['usuario_id'])
                    apostas_no_prazo_por_usuario[uid] = apostas_no_prazo_por_usuario.get(uid, 0) + 1
            except Exception:
                continue

    for idx, part in participantes.iterrows():
        apostas_part = apostas_df[apostas_df['usuario_id'] == part['id']].sort_values('prova_id')
        pontos_part = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df, temporada_descarte=season)
        total_provas = sum([p for p in pontos_part if p is not None])
        
        bonus_campeao = 0
        bonus_vice = 0
        bonus_equipe = 0
        acertou_campeao = 0
        acertou_vice = 0
        acertou_equipe = 0
        if resultado_campeonato:
            aposta_camp = get_championship_bet(part['id'], season)
            if aposta_camp:
                if resultado_campeonato.get("champion") == aposta_camp.get("champion"):
                    bonus_campeao = pontos_campeao
                    acertou_campeao = 1
                if resultado_campeonato.get("vice") == aposta_camp.get("vice"):
                    bonus_vice = pontos_vice
                    acertou_vice = 1
                if resultado_campeonato.get("team") == aposta_camp.get("team"):
                    bonus_equipe = pontos_equipe
                    acertou_equipe = 1
        pontos_campeonato = bonus_campeao + bonus_vice + bonus_equipe
        acertos_11 = int(acertos_11_por_usuario.get(part['id'], 0))
        apostas_no_prazo = int(apostas_no_prazo_por_usuario.get(part['id'], 0))
        
        tabela_classificacao.append({
            "Participante": part['nome'],
            "usuario_id": part['id'],
            "Pontos Provas": total_provas,
            "Bônus Campeão": bonus_campeao,
            "Bônus Vice": bonus_vice,
            "Bônus Equipe": bonus_equipe,
            "Pontos Campeonato": pontos_campeonato,
            "Total Geral": total_provas + pontos_campeonato,
            "Acertos 11": acertos_11,
            "Acertou Campeao": acertou_campeao,
            "Acertou Equipe": acertou_equipe,
            "Acertou Vice": acertou_vice,
            "Apostas no Prazo": apostas_no_prazo
        })
        tabela_detalhada.append({
            "Participante": part['nome'],
            "Pontos por Prova": pontos_part
        })

    df_class = pd.DataFrame(tabela_classificacao)
    if df_class.empty:
        st.info("Nenhuma pontuação disponível para a temporada selecionada.")
        return
    
    df_class = df_class.sort_values(
        ["Total Geral", "Acertos 11", "Acertou Campeao", "Acertou Equipe", "Acertou Vice", "Apostas no Prazo"],
        ascending=[False, False, False, False, False, False]
    ).reset_index(drop=True)
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
                "Total Geral": total_anteriores
            })
        df_class_anterior = pd.DataFrame(tabela_anterior)
        df_class_anterior = df_class_anterior.sort_values("Total Geral", ascending=False).reset_index(drop=True)
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
    
    diferencas = [0]
    totals = df_class["Total Geral"].tolist()
    for i in range(1, len(totals)):
        diferencas.append(totals[i-1] - totals[i])
    df_class["Diferença"] = ["-" if i == 0 else formatar_brasileiro(d) for i, d in enumerate(diferencas)]
    
    df_display = df_class.copy()
    for col in ["Pontos Provas", "Bônus Campeão", "Bônus Vice", "Bônus Equipe", "Pontos Campeonato", "Total Geral"]:
        df_display[col] = df_display[col].apply(lambda x: formatar_brasileiro(float(x)))
    
    colunas_ordem = [
        "Posição",
        "Participante",
        "Pontos Provas",
        "Bônus Campeão",
        "Bônus Vice",
        "Bônus Equipe",
        "Pontos Campeonato",
        "Total Geral",
        "Diferença",
        "Movimentação"
    ]
    st.subheader("Classificação Geral (Provas + Campeonato)")
    st.table(df_display[colunas_ordem])

    csv_classificacao = df_display[colunas_ordem].to_csv(index=False)
    st.download_button(
        label="Baixar tabela da classificação (CSV)",
        data=csv_classificacao,
        file_name="classificacao_geral.csv",
        mime="text/csv"
    )

    if perfil_usuario in ['admin', 'master']:
        imagem_buffer = gerar_imagem_tabela_ajustada(df_display, colunas_ordem)
        st.download_button(
            label='Baixar imagem da tabela',
            data=imagem_buffer,
            file_name='classificacao_geral.png',
            mime='image/png'
        )

    st.subheader("Pontuação por Prova")
    provas_df_ord = provas_df.sort_values('id')
    provas_nomes = provas_df_ord['nome'].tolist()
    provas_ids_ordenados = provas_df_ord['id'].tolist()
    dados_cruzados = {prova_nome: {} for prova_nome in provas_nomes}
    for part in tabela_detalhada:
        participante = part['Participante']
        pontos_por_prova = {}
        usr_id = df_class[df_class['Participante'] == participante]['usuario_id'].iloc[0]
        apostas_part = apostas_df[apostas_df['usuario_id'] == usr_id]
        for _, aposta in apostas_part.iterrows():
            p_list = calcular_pontuacao_lote(pd.DataFrame([aposta]), resultados_df, provas_df)
            if p_list:
                pontos_por_prova[aposta['prova_id']] = p_list[0]
        for prova_id, prova_nome in zip(provas_ids_ordenados, provas_nomes):
            pt = pontos_por_prova.get(prova_id, 0)
            dados_cruzados[prova_nome][participante] = pt if pt is not None else 0
    df_cruzada = pd.DataFrame(dados_cruzados).T
    df_cruzada = df_cruzada.reindex(
        columns=df_class['Participante'].tolist(),
        fill_value=0
    )
    df_formatado = df_cruzada.map(lambda x: formatar_brasileiro(float(x)))
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
        if isinstance(x, float): return x
        return float(str(x).replace('.', '').replace(',', '.'))
    df_grafico_float = df_grafico.map(texto_para_float)
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
        st.plotly_chart(fig, width="stretch")

    st.subheader("Classificação de Cada Participante ao Longo do Campeonato")
    with db_connect() as conn:
        query = 'SELECT * FROM posicoes_participantes WHERE temporada = ?'
        df_posicoes = pd.read_sql(query, conn, params=(season,))
        fig_all = go.Figure()
        for part in participantes['nome']:
            u_id = participantes[participantes['nome'] == part].iloc[0]['id']
            posicoes_part = df_posicoes[df_posicoes['usuario_id'] == u_id].sort_values('prova_id')
            if not posicoes_part.empty:
                x_vals = []
                for pid in posicoes_part['prova_id']:
                    p_name_arr = provas_df[provas_df['id'] == pid]['nome'].values
                    x_vals.append(p_name_arr[0] if len(p_name_arr) > 0 else f"ID {pid}")
                fig_all.add_trace(go.Scatter(
                    x=x_vals,
                    y=posicoes_part['posicao'],
                    mode='lines+markers',
                    name=part
                ))
        fig_all.update_yaxes(autorange="reversed")
        fig_all.update_layout(xaxis_title="Prova", yaxis_title="Posição", legend_title="Participante")
        st.plotly_chart(fig_all, width="stretch")

if __name__ == "__main__":
    main()
165
165
