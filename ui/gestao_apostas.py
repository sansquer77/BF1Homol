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
        show_df = apostas_df[["id", "usuario_id", "prova_id", "piloto_id", "pontos"]].copy()
        show_df.columns = ["ID", "Usuário ID", "Prova ID", "Piloto ID", "Pontos"]
        st.dataframe(show_df, use_container_width=True)
    
    # Divisor
    st.markdown("---")
    
    # Seção: Adicionar Nova Aposta
    st.markdown("### ➕ Adicionar Nova Aposta")
    
    usuarios_list = usuarios_df["nome"].tolist() if not usuarios_df.empty else []
    provas_list = provas_df["nome"].tolist() if not provas_df.empty else []
    pilotos_list = pilotos_df["nome"].tolist() if not pilotos_df.empty else []
    
    if usuarios_list and provas_list and pilotos_list:
        usuario_selecionado = st.selectbox("Selecione o usuário", usuarios_list, key="sel_usuario_aposta")
        prova_selecionada = st.selectbox("Selecione a prova", provas_list, key="sel_prova_aposta")
        piloto_selecionado = st.selectbox("Selecione o piloto", pilotos_list, key="sel_piloto_aposta")
        pontos_aposta = st.number_input("Pontos", min_value=0, max_value=100, value=0, key="pontos_aposta")
        
        if st.button("➕ Adicionar aposta", key="btn_add_aposta"):
            # Obter IDs
            usuario_id = usuarios_df[usuarios_df["nome"] == usuario_selecionado]["id"].values[0]
            prova_id = provas_df[provas_df["nome"] == prova_selecionada]["id"].values[0]
            piloto_id = pilotos_df[pilotos_df["nome"] == piloto_selecionado]["id"].values[0]
            
            # ✅ CORRIGIDO: Context manager com 'with'
            with db_connect() as conn:
                c = conn.cursor()
                c.execute(
                    '''INSERT INTO apostas (usuario_id, prova_id, piloto_id, pontos, temporada)
                       VALUES (?, ?, ?, ?, ?)''',
                    (usuario_id, prova_id, piloto_id, pontos_aposta, season)
                )
                conn.commit()
            
            st.success("✅ Aposta adicionada com sucesso!")
            st.cache_data.clear()
            st.rerun()
    else:
        st.warning("⚠️ Cadastre usuários, provas e pilotos antes de adicionar apostas.")

if __name__ == "__main__":
    main()
