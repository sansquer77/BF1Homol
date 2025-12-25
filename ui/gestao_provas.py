"""
Gestão de Provas - BF1Dev 3.0
Corrigido com context manager para pool de conexões
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from db.db_utils import get_provas_df, db_connect

def main():
    st.title("🏁 Gestão de Provas")
    
    # Verificar permissão
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return
    
    # Buscar TODAS as provas (sem filtro de temporada) para gestão
    with db_connect() as conn:
        df = pd.read_sql_query("SELECT * FROM provas ORDER BY data DESC", conn)
    
    # Seção: Provas Cadastradas
    if df.empty:
        st.info("Nenhuma prova cadastrada.")
    else:
        st.markdown("### 📋 Provas Cadastradas")
        cols_display = ["id", "nome", "data", "status"]
        col_names = ["ID", "Nome", "Data", "Status"]
        if "temporada" in df.columns:
            cols_display.append("temporada")
            col_names.append("Temporada")
        show_df = df[cols_display].copy()
        show_df.columns = col_names
        st.dataframe(show_df, use_container_width=True)
    
    # Seção: Editar Prova
    st.markdown("### ✏️ Editar Prova")
        # Inicializar variáveis para evitar NameError
    novo_nome = None
    nova_data = None
    horario_str = None
    novo_status = None
    novo_tipo = None
    nova_temporada = None
    if not df.empty:
        provas = df["nome"].tolist()
        selected = st.selectbox("Selecione uma prova para editar", provas, key="sel_prova_edit")
        prova_row = df[df["nome"] == selected].iloc[0]
        
        novo_nome = st.text_input("Nome da prova", prova_row["nome"], key="edit_nome_prova")
        novo_data = st.date_input("Data da prova", pd.to_datetime(prova_row["data"]).date(), key="edit_data_prova")
        
        # Horário da prova
        horario_atual = prova_row.get("horario_prova", "14:00:00")
        try:
            horario_time = pd.to_datetime(horario_atual, format="%H:%M:%S").time()
        except Exception:
            horario_time = pd.to_datetime("14:00:00", format="%H:%M:%S").time()
        novo_horario = st.time_input(
            "Horário da prova (Fuso Horário: São Paulo/Brasil - Bloqueio de apostas após este horário)",
            horario_time,
            key="edit_horario_prova",
            help="Horário em formato 24h (ex: 14:00 para 2 PM). Apostas serão bloqueadas após este horário em qualquer fuso horário."
        )
        
        # Normalize status options to Ativa/Inativa for new UX. If stored value is different, fall back to first option.
        status_options = ["Ativa", "Inativa"]
        try:
            status_index = status_options.index(prova_row.get("status", "Ativa"))
        except ValueError:
            status_index = 0
        novo_status = st.selectbox(
            "Status",
            status_options,
            index=status_index,
            key="edit_status_prova"
        )

        # Tipo da prova (Normal / Sprint)
        tipo_options = ["Normal", "Sprint"]
        tipo_current = prova_row.get("tipo", "Normal")
        tipo_index = tipo_options.index(tipo_current) if tipo_current in tipo_options else 0
        novo_tipo = st.selectbox("Tipo", tipo_options, index=tipo_index, key="edit_tipo_prova")
        
        # Temporada
        from db.backup_utils import list_temporadas
        temporadas = list_temporadas()
        current_year = datetime.now().year
        if str(current_year) not in temporadas:
            temporadas.append(str(current_year))
        temporadas = sorted(temporadas)
        temporada_atual = str(prova_row.get("temporada", current_year))
        if temporada_atual not in temporadas:
            temporadas.append(temporada_atual)
            temporadas = sorted(temporadas)
        temporada_index = temporadas.index(temporada_atual) if temporada_atual in temporadas else 0
        nova_temporada = st.selectbox("Temporada", temporadas, index=temporada_index, key="edit_temporada_prova")
        
        col1, col2 = st.columns(2)
        
        # Botão: Atualizar
        with col1:
            if st.button("🔄 Atualizar prova", key="btn_update_prova"):
                horario_str = novo_horario.strftime("%H:%M:%S")
                with db_connect() as conn:
                    c = conn.cursor()
                    # Check if temporada column exists
                    c.execute("PRAGMA table_info('provas')")
                    cols = [r[1] for r in c.fetchall()]
                    if "temporada" in cols:
                        c.execute(
                            "UPDATE provas SET nome=?, data=?, horario_prova=?, status=?, tipo=?, temporada=? WHERE id=?",
                            (novo_nome, (nova_data.strftime('%Y-%m-%d') if nova_data is not None else str(prova_row["data"])), horario_str, novo_status, novo_tipo, nova_temporada, int(prova_row["id"]))
                        )
                    else:
                        c.execute(
                            "UPDATE provas SET nome=?, data=?, horario_prova=?, status=?, tipo=? WHERE id=?",
                            (novo_nome, (nova_data.strftime('%Y-%m-%d') if nova_data is not None else str(prova_row["data"])), horario_str, novo_status, novo_tipo, int(prova_row["id"]))
                        )
                    conn.commit()
                
                st.success("✅ Prova atualizada com sucesso!")
                st.cache_data.clear()
                st.rerun()
        
        # Botão: Excluir
        with col2:
            if st.button("🗑️ Excluir prova", key="btn_delete_prova"):
                with db_connect() as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM provas WHERE id=?", (int(prova_row["id"]),))
                    conn.commit()
                
                st.success("✅ Prova excluída com sucesso!")
                st.cache_data.clear()
                st.rerun()
    
    # Divisor
    st.markdown("---")
    
    # Seção: Adicionar Nova Prova
    st.markdown("### ➕ Adicionar Nova Prova")
    
    nome_novo = st.text_input("Nome da nova prova", key="novo_nome_prova")
    data_nova = st.date_input("Data da prova", key="nova_data_prova")
    horario_novo = st.time_input(
        "Horário da prova (Fuso Horário: São Paulo/Brasil - Bloqueio de apostas após este horário)",
        pd.to_datetime("14:00:00", format="%H:%M:%S").time(),
        key="novo_horario_prova",
        help="Horário em formato 24h (ex: 14:00 para 2 PM). Apostas serão bloqueadas após este horário em qualquer fuso horário."
    )
    status_novo = st.selectbox("Status", ["Ativa", "Inativa"], key="novo_status_prova")
    tipo_novo = st.selectbox("Tipo", ["Normal", "Sprint"], key="novo_tipo_prova")
    
    # Temporada
    from db.backup_utils import list_temporadas
    temporadas_add = list_temporadas()
    current_year = datetime.now().year
    if str(current_year) not in temporadas_add:
        temporadas_add.append(str(current_year))
    temporadas_add = sorted(temporadas_add)
    temporada_index_add = temporadas_add.index(str(current_year)) if str(current_year) in temporadas_add else 0
    temporada_nova = st.selectbox("Temporada", temporadas_add, index=temporada_index_add, key="nova_temporada_prova")
    
    if st.button("➕ Adicionar prova", key="btn_add_prova"):
        if not nome_novo:
            st.error("❌ Preencha o nome da prova.")
        else:
            horario_str_novo = horario_novo.strftime("%H:%M:%S")
            with db_connect() as conn:
                c = conn.cursor()
                # Check if temporada column exists
                c.execute("PRAGMA table_info('provas')")
                cols = [r[1] for r in c.fetchall()]
                
                # Verificar duplicidade (nome + data + temporada)
                if "temporada" in cols:
                    c.execute(
                        "SELECT COUNT(*) FROM provas WHERE nome = ? AND data = ? AND temporada = ?",
                        (nome_novo, data_nova, temporada_nova)
                    )
                else:
                    c.execute(
                        "SELECT COUNT(*) FROM provas WHERE nome = ? AND data = ?",
                        (nome_novo, data_nova)
                    )
                
                if c.fetchone()[0] > 0:
                    st.error(f"❌ Já existe uma prova cadastrada com este nome e data para a temporada {temporada_nova}.")
                else:
                    # Inserir nova prova
                    if "temporada" in cols:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo, temporada)
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (nome_novo, data_nova, horario_str_novo, status_novo, tipo_novo, temporada_nova)
                        )
                    else:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo)
                               VALUES (?, ?, ?, ?, ?)''',
                            (nome_novo, data_nova, horario_str_novo, status_novo, tipo_novo)
                        )
                    conn.commit()
                    st.success("✅ Prova adicionada com sucesso!")
                    st.cache_data.clear()
                    st.rerun()

if __name__ == "__main__":
    main()
