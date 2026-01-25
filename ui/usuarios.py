import streamlit as st
import pandas as pd
from db.db_utils import get_usuarios_df, db_connect
from services.auth_service import hash_password

def main():
    st.title("👥 Gestão de Usuários")

    # Definir permissões necessárias: apenas master pode editar tudo, admin pode ver; participante não acessa
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    df = get_usuarios_df()
    if df.empty:
        st.info("Nenhum usuário cadastrado.")
        return

    st.markdown("### Usuários Cadastrados")
    with st.expander("Lista Completa de Usuários", expanded=True):
        show_df = df[["id", "nome", "email", "perfil", "status"]].copy()
        show_df.columns = ["ID", "Nome", "Email", "Perfil", "Status"]
        st.dataframe(show_df, use_container_width=True)

    st.markdown("### Editar Usuário")

    usuarios = df["nome"].tolist()
    selected = st.selectbox("Selecione um usuário para editar", usuarios)
    user_row = df[df["nome"] == selected].iloc[0]

    # Campos de edição
    novo_nome = st.text_input("Nome", user_row["nome"])
    novo_email = st.text_input("Email", user_row["email"])
    novo_perfil = st.selectbox("Perfil", ["participante", "admin", "master"], index=["participante", "admin", "master"].index(user_row["perfil"]))
    novo_status = st.selectbox("Status", ["Ativo", "Inativo"], index=0 if user_row["status"] == "Ativo" else 1)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Atualizar usuário"):
            with db_connect() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE usuarios SET nome=?, email=?, perfil=?, status=? WHERE id=?",
                    (novo_nome, novo_email, novo_perfil, novo_status, int(user_row["id"]))
                )
                conn.commit()
            st.success("Usuário atualizado!")
            st.cache_data.clear()
            st.rerun()

    with col2:
        if "alterar_senha" not in st.session_state:
            st.session_state["alterar_senha"] = False

        if st.button("Alterar senha do usuário"):
            st.session_state["alterar_senha"] = True

        if st.session_state["alterar_senha"]:
            nova_senha = st.text_input("Nova senha", type="password", key="senha_reset")
            if st.button("Salvar nova senha"):
                if not nova_senha:
                    st.error("Digite a nova senha.")
                else:
                    nova_hash = hash_password(nova_senha)
                    with db_connect() as conn:
                        c = conn.cursor()
                        c.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (nova_hash, int(user_row["id"])))
                        conn.commit()
                    st.success("Senha atualizada com sucesso!")
                    st.session_state["alterar_senha"] = False
security: add email and password validation to user management

Use utils.validators in the user management interface to ensure that new
users are created with valid email formats and strong passwords. This
addresses vulnerabilities related to predictable/default credentials.                    st.rerun()
            if st.button("Cancelar alteração de senha"):
                st.session_state["alterar_senha"] = False

    st.markdown("### Excluir usuário")
    if perfil == "master":
        if st.button("Excluir usuário selecionado"):
            if user_row["perfil"] == "master":
                st.error("Não é possível excluir um usuário master.")
            else:
                    with db_connect() as conn:
                        c = conn.cursor()
                        c.execute("DELETE FROM usuarios WHERE id=?", (int(user_row["id"]),))
                        conn.commit()
                    st.success("Usuário excluído com sucesso!")
                    st.cache_data.clear()
                    st.rerun()

    st.markdown("---")
    st.markdown("### Adicionar Novo Usuário")
    nome_novo = st.text_input("Nome completo", key="novo_nome")
    email_novo = st.text_input("Email", key="novo_email")
    senha_novo = st.text_input("Senha", type="password", key="nova_senha")
    perfil_novo = st.selectbox("Perfil", ["participante", "admin", "master"], key="novo_perfil")
    status_novo = st.selectbox("Status", ["Ativo", "Inativo"], key="novo_status")

    if st.button("Adicionar usuário"):
        if not nome_novo or not email_novo or not senha_novo:
            st.error("Preencha todos os campos obrigatórios.")
        else:
            from services.auth_service import cadastrar_usuario
            sucesso = cadastrar_usuario(nome_novo, email_novo, senha_novo, perfil=perfil_novo, status=status_novo)
            if sucesso:
                st.success("Usuário adicionado com sucesso!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Email já cadastrado.")

if __name__ == "__main__":
    main()
