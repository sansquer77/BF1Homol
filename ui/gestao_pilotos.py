import streamlit as st
import pandas as pd
from db.db_utils import get_pilotos_df, db_connect

def main():
    st.title("🏎️ Gestão de Pilotos")

    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    df = get_pilotos_df().sort_values(by="nome")
    if df.empty:
        st.info("Nenhum piloto cadastrado.")
    else:
        st.markdown("### Pilotos Cadastrados")
        show_df = df[["id", "nome", "equipe", "status"]].copy()
        show_df.columns = ["ID", "Nome", "Equipe", "Status"]
        st.dataframe(show_df, use_container_width=True)

    st.markdown("### Editar Piloto")
    if not df.empty:
        pilotos = df["nome"].tolist()
        selected = st.selectbox("Selecione um piloto para editar", pilotos, key="sel_piloto_edit")
        piloto_row = df[df["nome"] == selected].iloc[0]
        novo_nome = st.text_input("Nome do piloto", piloto_row["nome"], key="edit_nome_piloto")
        nova_equipe = st.text_input("Equipe", piloto_row["equipe"], key="edit_equipe_piloto")
        novo_status = st.selectbox("Status", ["Ativo", "Inativo"], index=0 if piloto_row["status"] == "Ativo" else 1, key="edit_status_piloto")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Atualizar piloto", key="btn_update_piloto"):
                conn = db_connect()
                c = conn.cursor()
                c.execute(
                    "UPDATE pilotos SET nome=?, equipe=?, status=? WHERE id=?",
                    (novo_nome, nova_equipe, novo_status, int(piloto_row["id"]))
                )
                conn.commit()
                conn.close()
                st.success("Piloto atualizado!")
                st.cache_data.clear()
                st.rerun()
        with col2:
            if st.button("Excluir piloto", key="btn_delete_piloto"):
                conn = db_connect()
                c = conn.cursor()
                c.execute("DELETE FROM pilotos WHERE id=?", (int(piloto_row["id"]),))
                conn.commit()
                conn.close()
                st.success("Piloto excluído com sucesso!")
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    st.markdown("### Adicionar Novo Piloto")
    nome_novo = st.text_input("Nome do novo piloto", key="novo_nome_piloto")
    equipe_nova = st.text_input("Equipe do novo piloto", key="nova_equipe_piloto")
    status_novo = st.selectbox("Status", ["Ativo", "Inativo"], key="novo_status_piloto")

    if st.button("Adicionar piloto", key="btn_add_piloto"):
        if not nome_novo or not equipe_nova:
            st.error("Preencha todos os campos obrigatórios.")
        else:
            conn = db_connect()
            c = conn.cursor()
            c.execute(
                '''INSERT INTO pilotos (nome, equipe, status)
                   VALUES (?, ?, ?)''',
                (nome_novo, equipe_nova, status_novo)
            )
            conn.commit()
            conn.close()
            st.success("Piloto adicionado com sucesso!")
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    main()
