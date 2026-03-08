"""
Gestão de Provas - BF1 3.0
Corrigido com context manager para pool de conexões
Reorganizado em abas: Editar Provas / Adicionar Nova Prova
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from db.db_utils import get_provas_df, db_connect
from utils.season_utils import get_default_season_index, get_season_options


def _on_prova_change():
    """Callback para limpar os valores do formulário quando a prova selecionada mudar."""
    # Limpar os valores armazenados para forçar atualização do formulário
    keys_to_clear = [
        "edit_nome_prova_val", "edit_data_prova_val", "edit_horario_prova_val",
        "edit_status_prova_val", "edit_tipo_prova_val", "edit_temporada_prova_val"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def _render_tabela_provas(df: pd.DataFrame):
    """Renderiza a tabela de provas cadastradas."""
    if df.empty:
        st.info("Nenhuma prova cadastrada.")
        return
    
    st.markdown("### 📋 Provas Cadastradas")
    cols_display = ["id", "nome", "data", "status"]
    col_names = ["ID", "Nome", "Data", "Status"]
    
    # Adicionar coluna Tipo
    if "tipo" in df.columns:
        cols_display.append("tipo")
        col_names.append("Tipo")
    
    # Adicionar coluna Temporada
    if "temporada" in df.columns:
        cols_display.append("temporada")
        col_names.append("Temporada")
    
    show_df = df[cols_display].copy()
    show_df.columns = col_names
    st.dataframe(show_df, width="stretch")


def _render_aba_editar(df: pd.DataFrame):
    """Renderiza a aba de edição de provas existentes."""
    # Tabela de provas
    _render_tabela_provas(df)
    
    st.markdown("---")
    st.markdown("### ✏️ Editar Prova Selecionada")
    
    if df.empty:
        st.warning("Não há provas para editar. Adicione uma prova na aba 'Adicionar Nova Prova'.")
        return
    
    # Criar lista de opções com ID para evitar ambiguidade
    df["opcao_display"] = df.apply(
        lambda r: f"{r['nome']} ({r['data']}) - ID: {r['id']}", axis=1
    )
    opcoes = df["opcao_display"].tolist()
    
    # Selectbox com callback para atualizar formulário
    selected = st.selectbox(
        "Selecione uma prova para editar",
        opcoes,
        key="sel_prova_edit",
        on_change=_on_prova_change
    )
    
    # Encontrar a prova selecionada
    prova_row = df[df["opcao_display"] == selected].iloc[0]
    prova_id = int(prova_row["id"])
    
    # Obter valores da prova selecionada
    nome_atual = prova_row["nome"]
    data_atual = pd.to_datetime(prova_row["data"]).date()
    
    horario_atual = prova_row.get("horario_prova", "14:00:00")
    try:
        horario_time = pd.to_datetime(str(horario_atual), format="%H:%M:%S").time()
    except Exception:
        horario_time = pd.to_datetime("14:00:00", format="%H:%M:%S").time()
    
    status_atual = prova_row.get("status", "Ativa")
    tipo_atual = prova_row.get("tipo", "Normal")
    
    current_year = str(datetime.now().year)
    temporada_atual = str(prova_row.get("temporada", current_year))
    temporadas = get_season_options(ensure_values=[temporada_atual])
    
    # Formulário de edição - usar key única baseada no ID da prova
    novo_nome = st.text_input(
        "Nome da prova",
        value=nome_atual,
        key=f"edit_nome_prova_{prova_id}"
    )
    
    nova_data = st.date_input(
        "Data da prova",
        value=data_atual,
        key=f"edit_data_prova_{prova_id}"
    )
    
    novo_horario = st.time_input(
        "Horário da prova (Fuso Horário: São Paulo/Brasil - Bloqueio de apostas após este horário)",
        value=horario_time,
        key=f"edit_horario_prova_{prova_id}",
        help="Horário em formato 24h (ex: 14:00 para 2 PM). Apostas serão bloqueadas após este horário em qualquer fuso horário."
    )
    
    status_options = ["Ativa", "Inativa"]
    try:
        status_index = status_options.index(status_atual)
    except ValueError:
        status_index = 0
    novo_status = st.selectbox(
        "Status",
        status_options,
        index=status_index,
        key=f"edit_status_prova_{prova_id}"
    )
    
    tipo_options = ["Normal", "Sprint"]
    tipo_index = tipo_options.index(tipo_atual) if tipo_atual in tipo_options else 0
    novo_tipo = st.selectbox(
        "Tipo",
        tipo_options,
        index=tipo_index,
        key=f"edit_tipo_prova_{prova_id}"
    )
    
    temporada_index = temporadas.index(temporada_atual) if temporada_atual in temporadas else 0
    nova_temporada = st.selectbox(
        "Temporada",
        temporadas,
        index=temporada_index,
        key=f"edit_temporada_prova_{prova_id}"
    )
    
    col1, col2 = st.columns(2)
    
    # Botão: Atualizar
    with col1:
        if st.button("🔄 Atualizar prova", key="btn_update_prova", type="primary"):
            horario_str = novo_horario.strftime("%H:%M:%S")
            with db_connect() as conn:
                c = conn.cursor()
                c.execute("PRAGMA table_info('provas')")
                cols = [r[1] for r in c.fetchall()]
                if "temporada" in cols:
                    c.execute(
                        "UPDATE provas SET nome=?, data=?, horario_prova=?, status=?, tipo=?, temporada=? WHERE id=?",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, nova_temporada, prova_id)
                    )
                else:
                    c.execute(
                        "UPDATE provas SET nome=?, data=?, horario_prova=?, status=?, tipo=? WHERE id=?",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, prova_id)
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
                c.execute("DELETE FROM provas WHERE id=?", (prova_id,))
                conn.commit()
            
            st.success("✅ Prova excluída com sucesso!")
            st.cache_data.clear()
            st.rerun()


def _render_aba_adicionar():
    """Renderiza a aba de adicionar nova prova."""
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
    current_year = str(datetime.now().year)
    temporadas_add = get_season_options()
    temporada_index_add = get_default_season_index(temporadas_add, current_year=current_year)
    temporada_nova = st.selectbox("Temporada", temporadas_add, index=temporada_index_add, key="nova_temporada_prova")
    
    if st.button("➕ Adicionar prova", key="btn_add_prova", type="primary"):
        if not nome_novo:
            st.error("❌ Preencha o nome da prova.")
        else:
            horario_str_novo = horario_novo.strftime("%H:%M:%S")
            with db_connect() as conn:
                c = conn.cursor()
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


def main():
    st.title("🏁 Gestão de Provas")
    
    # Verificar permissão
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return
    
    # Filtro por temporada
    current_year = str(datetime.now().year)
    temporadas = get_season_options()
    default_index = get_default_season_index(temporadas, current_year=current_year)
    temporada_sel = st.selectbox("Temporada", temporadas, index=default_index, key="gestao_provas_temporada")

    # Buscar provas filtradas por temporada (ordenadas por data crescente)
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('provas')")
        cols = [r[1] for r in c.fetchall()]
        if 'temporada' in cols:
            df = pd.read_sql_query(
                "SELECT * FROM provas WHERE temporada = ? OR temporada IS NULL ORDER BY data ASC",
                conn,
                params=(temporada_sel,)
            )
        else:
            df = pd.read_sql_query("SELECT * FROM provas ORDER BY data ASC", conn)
    
    # Criar abas
    tab_editar, tab_adicionar = st.tabs(["✏️ Editar Provas", "➕ Adicionar Nova Prova"])
    
    with tab_editar:
        _render_aba_editar(df)
    
    with tab_adicionar:
        _render_aba_adicionar()


if __name__ == "__main__":
    main()
