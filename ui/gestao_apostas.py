"""
Gestão de Apostas - BF1Dev 3.0
Corrigido com context manager para pool de conexões e suporte a temporadas
"""

import streamlit as st
import pandas as pd
import datetime as dt
from db.db_utils import get_apostas_df, get_usuarios_df, get_provas_df, get_pilotos_df, db_connect
from db.backup_utils import list_temporadas

def main():
    st.title("💰 Gestão de Apostas")
    
    # Verificar permissão
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return
    
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
    
    season = st.selectbox("Temporada", season_options, index=default_index, key="gestao_apostas_season")
    st.session_state['temporada'] = season
    
    # Buscar dados com cache e filtro de temporada
    apostas_df = get_apostas_df(season)
    usuarios_df = get_usuarios_df()
    provas_df = get_provas_df(season)
    pilotos_df = get_pilotos_df()
    
    # Seção: Apostas Cadastradas
    if apostas_df.empty:
        st.info("Nenhuma aposta cadastrada.")
    else:
        st.markdown("### 📋 Apostas Cadastradas")
        # Mostrar apenas colunas que existem no schema real
        available_cols = [col for col in ["id", "usuario_id", "prova_id", "data_envio", "pilotos", "temporada"] 
                         if col in apostas_df.columns]
        show_df = apostas_df[available_cols].copy() if available_cols else apostas_df.copy()
        st.dataframe(show_df, use_container_width=True)
    
    # Divisor
    st.markdown("---")
    
    # Seção: Adicionar Classificação Manual (Posição)
    st.markdown("### ➕ Adicionar Classificação Manual")
    st.info("ℹ️ Adicione a posição de um participante em uma prova (sistema de pontuação)")
    
    usuarios_list = usuarios_df["nome"].tolist() if not usuarios_df.empty else []
    provas_list = provas_df["nome"].tolist() if not provas_df.empty else []
    
    if usuarios_list and provas_list:
        col1, col2, col3 = st.columns(3)
        with col1:
            usuario_selecionado = st.selectbox("Selecione o usuário", usuarios_list, key="sel_usuario_classif")
        with col2:
            prova_selecionada = st.selectbox("Selecione a prova", provas_list, key="sel_prova_classif")
        with col3:
            posicao_classif = st.number_input("Posição", min_value=1, max_value=50, value=1, key="pos_classif")
        
        pontos_classif = st.number_input("Pontos", min_value=0, max_value=100, value=0, key="pontos_classif")
        
        if st.button("➕ Adicionar classificação", key="btn_add_classif"):
            # Obter IDs
            usuario_id = usuarios_df[usuarios_df["nome"] == usuario_selecionado]["id"].values[0]
            prova_id = provas_df[provas_df["nome"] == prova_selecionada]["id"].values[0]
            
            # ✅ CORRIGIDO: Inserir em posicoes_participantes (estrutura correta)
            from datetime import datetime
            data_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with db_connect() as conn:
                c = conn.cursor()
                c.execute(
                    '''INSERT OR REPLACE INTO posicoes_participantes 
                       (prova_id, usuario_id, posicao, pontos, data_registro, temporada)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (prova_id, usuario_id, posicao_classif, pontos_classif, data_registro, season)
                )
                conn.commit()
            
            st.success("✅ Classificação adicionada com sucesso!")
            st.cache_data.clear()
            st.rerun()
    else:
        st.warning("⚠️ Cadastre usuários e provas antes de adicionar classificações.")

if __name__ == "__main__":
    main()
