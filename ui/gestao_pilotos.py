"""
Gestão de Pilotos - BF1Dev 3.0
Corrigido com context manager para pool de conexões
Reorganizado em abas: Editar Pilotos / Adicionar Novo Piloto
"""

import streamlit as st
import pandas as pd
from db.db_utils import get_pilotos_df, db_connect


def _on_piloto_change():
    """Callback para limpar os valores do formulário quando o piloto selecionado mudar."""
    keys_to_clear = [
        "edit_nome_piloto_val", "edit_numero_piloto_val", 
        "edit_equipe_piloto_val", "edit_status_piloto_val"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def _render_tabela_pilotos(df: pd.DataFrame):
    """Renderiza a tabela de pilotos cadastrados."""
    if df.empty:
        st.info("Nenhum piloto cadastrado.")
        return
    
    st.markdown("### 📋 Pilotos Cadastrados")
    cols_to_show = ["id", "nome"]
    col_names = ["ID", "Nome"]
    if "numero" in df.columns:
        cols_to_show.append("numero")
        col_names.append("Número")
    cols_to_show.extend(["equipe", "status"])
    col_names.extend(["Equipe", "Status"])
    
    show_df = df[cols_to_show].copy()
    show_df.columns = col_names
    st.dataframe(show_df, use_container_width=True)


def _render_aba_editar(df: pd.DataFrame):
    """Renderiza a aba de edição de pilotos existentes."""
    # Tabela de pilotos
    _render_tabela_pilotos(df)
    
    st.markdown("---")
    st.markdown("### ✏️ Editar Piloto Selecionado")
    
    if df.empty:
        st.warning("Não há pilotos para editar. Adicione um piloto na aba 'Adicionar Novo Piloto'.")
        return
    
    # Criar lista de opções com ID para evitar ambiguidade
    df["opcao_display"] = df.apply(
        lambda r: f"{r['nome']} ({r.get('equipe', 'Sem equipe')}) - ID: {r['id']}", axis=1
    )
    opcoes = df["opcao_display"].tolist()
    
    # Selectbox com callback para atualizar formulário
    selected = st.selectbox(
        "Selecione um piloto para editar",
        opcoes,
        key="sel_piloto_edit",
        on_change=_on_piloto_change
    )
    
    # Encontrar o piloto selecionado
    piloto_row = df[df["opcao_display"] == selected].iloc[0]
    piloto_id = int(piloto_row["id"])
    
    # Obter valores do piloto selecionado
    nome_atual = piloto_row["nome"]
    numero_atual = int(piloto_row.get("numero", 0)) if piloto_row.get("numero") is not None else 0
    equipe_atual = piloto_row.get("equipe", "")
    status_atual = piloto_row.get("status", "Ativo")
    
    # Formulário de edição - usar key única baseada no ID do piloto
    novo_nome = st.text_input(
        "Nome do piloto",
        value=nome_atual,
        key=f"edit_nome_piloto_{piloto_id}"
    )
    
    novo_numero = st.number_input(
        "Número do piloto",
        value=numero_atual,
        min_value=0,
        step=1,
        key=f"edit_numero_piloto_{piloto_id}"
    )
    
    nova_equipe = st.text_input(
        "Equipe",
        value=equipe_atual,
        key=f"edit_equipe_piloto_{piloto_id}"
    )
    
    status_options = ["Ativo", "Inativo"]
    status_index = status_options.index(status_atual) if status_atual in status_options else 0
    novo_status = st.selectbox(
        "Status",
        status_options,
        index=status_index,
        key=f"edit_status_piloto_{piloto_id}"
    )
    
    col1, col2 = st.columns(2)
    
    # Botão: Atualizar
    with col1:
        if st.button("🔄 Atualizar piloto", key="btn_update_piloto", type="primary"):
            with db_connect() as conn:
                c = conn.cursor()
                if novo_status == "Ativo":
                    c.execute(
                        "SELECT id FROM pilotos WHERE LOWER(nome) = LOWER(?) AND status = 'Ativo' AND id != ?",
                        (novo_nome, piloto_id)
                    )
                    if c.fetchone():
                        st.error("❌ Já existe outro piloto ativo com este nome.")
                        return
                else:
                    c.execute(
                        "SELECT id FROM pilotos WHERE LOWER(nome) = LOWER(?) AND numero = ? AND LOWER(equipe) = LOWER(?) AND status = 'Inativo' AND id != ?",
                        (novo_nome, int(novo_numero), nova_equipe, piloto_id)
                    )
                    if c.fetchone():
                        st.error("❌ Já existe outro piloto inativo com este nome, número e equipe.")
                        return
                
                c.execute(
                    "UPDATE pilotos SET nome=?, numero=?, equipe=?, status=? WHERE id=?",
                    (novo_nome, int(novo_numero), nova_equipe, novo_status, piloto_id)
                )
                conn.commit()
            
            st.success("✅ Piloto atualizado com sucesso!")
            st.cache_data.clear()
            st.rerun()
    
    # Botão: Excluir
    with col2:
        if st.button("🗑️ Excluir piloto", key="btn_delete_piloto"):
            with db_connect() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM pilotos WHERE id=?", (piloto_id,))
                conn.commit()
            
            st.success("✅ Piloto excluído com sucesso!")
            st.cache_data.clear()
            st.rerun()


def _render_aba_adicionar():
    """Renderiza a aba de adicionar novo piloto."""
    st.markdown("### ➕ Adicionar Novo Piloto")
    
    nome_novo = st.text_input("Nome do novo piloto", key="novo_nome_piloto")
    numero_novo = st.number_input("Número do piloto", min_value=0, step=1, key="novo_numero_piloto")
    equipe_nova = st.text_input("Equipe do novo piloto", key="nova_equipe_piloto")
    status_novo = st.selectbox("Status", ["Ativo", "Inativo"], key="novo_status_piloto")
    
    if st.button("➕ Adicionar piloto", key="btn_add_piloto", type="primary"):
        if not nome_novo or not equipe_nova:
            st.error("❌ Preencha todos os campos obrigatórios.")
        else:
            with db_connect() as conn:
                c = conn.cursor()
                
                if status_novo == "Ativo":
                    c.execute(
                        "SELECT id FROM pilotos WHERE LOWER(nome) = LOWER(?) AND status = 'Ativo'",
                        (nome_novo,)
                    )
                    if c.fetchone():
                        st.error("❌ Já existe outro piloto ativo com este nome.")
                        return
                else:
                    c.execute(
                        "SELECT id FROM pilotos WHERE LOWER(nome) = LOWER(?) AND numero = ? AND LOWER(equipe) = LOWER(?) AND status = 'Inativo'",
                        (nome_novo, int(numero_novo), equipe_nova)
                    )
                    if c.fetchone():
                        st.error("❌ Já existe outro piloto inativo com este nome, número e equipe.")
                        return
                
                c.execute(
                    '''INSERT INTO pilotos (nome, numero, equipe, status)
                       VALUES (?, ?, ?, ?)''',
                    (nome_novo, int(numero_novo), equipe_nova, status_novo)
                )
                conn.commit()
            
            st.success("✅ Piloto adicionado com sucesso!")
            st.cache_data.clear()
            st.rerun()


def main():
    st.title("🏎️ Gestão de Pilotos")
    
    # Verificar permissão
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return
    
    # Buscar pilotos com cache
    df = get_pilotos_df().sort_values(by="nome")
    
    # Criar abas
    tab_editar, tab_adicionar = st.tabs(["✏️ Editar Pilotos", "➕ Adicionar Novo Piloto"])
    
    with tab_editar:
        _render_aba_editar(df)
    
    with tab_adicionar:
        _render_aba_adicionar()


if __name__ == "__main__":
    main()
