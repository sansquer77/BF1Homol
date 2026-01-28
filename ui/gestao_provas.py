import streamlit as st
import pandas as pd
from db.db_utils import get_provas_df, db_connect
from datetime import datetime

def main():
    st.title("🏁 Gestão de Provas")

    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    df = get_provas_df().sort_values(by="data")
    if df.empty:
        st.info("Nenhuma prova cadastrada.")
    else:
        st.markdown("### Provas Cadastradas")
        show_df = df[["id", "nome", "data", "horario_prova", "tipo", "status"]].copy()
        show_df.columns = ["ID", "Nome", "Data", "Horário", "Tipo", "Status"]
        st.dataframe(show_df, use_container_width=True)

    st.markdown("### Editar Prova")
    if not df.empty:
        provas = df["nome"].tolist()
        selected = st.selectbox("Selecione uma prova para editar", provas, key="sel_prova_edit")
        prova_row = df[df["nome"] == selected].iloc[0]
        novo_nome = st.text_input("Nome da prova", prova_row["nome"], key="edit_nome")
        nova_data = st.date_input(
            "Data", 
            datetime.strptime(prova_row["data"], "%Y-%m-%d") if prova_row["data"] else datetime.now(),
            key="edit_data"
        )
        novo_horario = st.text_input("Horário (HH:MM:SS)", prova_row["horario_prova"], key="edit_horario")
        novo_tipo = st.selectbox("Tipo", ["Normal", "Sprint"], index=0 if prova_row["tipo"] == "Normal" else 1, key="edit_tipo")
        novo_status = st.selectbox("Status", ["Ativo", "Inativo"], index=0 if prova_row["status"] == "Ativo" else 1, key="edit_status")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Atualizar prova", key="btn_update_prova"):
                conn = db_connect()
                c = conn.cursor()
                c.execute(
                    "UPDATE provas SET nome=?, data=?, horario_prova=?, tipo=?, status=? WHERE id=?",
                    (novo_nome, nova_data.strftime("%Y-%m-%d"), novo_horario, novo_tipo, novo_status, int(prova_row["id"]))
                )
                conn.commit()
                conn.close()
                st.success("Prova atualizada!")
                st.cache_data.clear()
                st.rerun()
        with col2:
            if st.button("Excluir prova", key="btn_delete_prova"):
                conn = db_connect()
                c = conn.cursor()
                c.execute("DELETE FROM provas WHERE id=?", (int(prova_row["id"]),))
                conn.commit()
                conn.close()
                st.success("Prova excluída com sucesso!")
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    st.markdown("### Adicionar Nova Prova")
    nome_novo = st.text_input("Nome da nova prova", key="novo_nome_prova")
    data_nova = st.date_input("Data", datetime.now(), key="nova_data_prova")
    horario_novo = st.text_input("Horário (HH:MM:SS)", value="10:00:00", key="novo_horario_prova")
    tipo_novo = st.selectbox("Tipo", ["Normal", "Sprint"], key="novo_tipo_prova")
    status_novo = st.selectbox("Status", ["Ativo", "Inativo"], key="novo_status_prova")

    if st.button("Adicionar prova", key="btn_add_prova"):
        if not nome_novo or not horario_novo or not data_nova:
            st.error("Preencha todos os campos obrigatórios.")
        else:
            conn = db_connect()
            c = conn.cursor()
            c.execute(
                '''INSERT INTO provas (nome, data, horario_prova, tipo, status)
                   VALUES (?, ?, ?, ?, ?)''',
                (nome_novo, data_nova.strftime("%Y-%m-%d"), horario_novo, tipo_novo, status_novo)
            )
            conn.commit()
            conn.close()
            st.success("Prova adicionada com sucesso!")
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    main()
