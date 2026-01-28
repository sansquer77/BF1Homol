import streamlit as st
from services.auth_service import (
    autenticar_usuario,
    cadastrar_usuario,
    generate_token,
    get_user_by_email,
    hash_password,
    redefinir_senha_usuario
)
from services.email_service import enviar_email_recuperacao_senha
from datetime import datetime, timedelta
import extra_streamlit_components as stx

def logout():
    cookie_manager = stx.CookieManager()
    cookie_manager.delete("session_token")
    for k in ["token", "user_id", "user_name", "user_role", "pagina"]:
        if k in st.session_state:
            del st.session_state[k]
    st.success("Logout realizado com sucesso!")
    st.experimental_rerun()

def login_view():
    col1, col2 = st.columns([1, 16])  # Proporção ajustável conforme aparência desejada
    with col1:
        st.image("BF1.jpg", width=75)
    with col2:
        st.title("Login do BF1")
    
    if "esqueceu_senha" not in st.session_state:
        st.session_state["esqueceu_senha"] = False
    if "criar_usuario" not in st.session_state:
        st.session_state["criar_usuario"] = False

    cookie_manager = stx.CookieManager()

    if st.session_state.get("token"):
        if st.button("Logout", key="btn_logout"):
            logout()
        st.stop()

    if st.session_state.get("logout", False):
        cookie_manager.delete("session_token")
        st.session_state["logout"] = False

    if not st.session_state["esqueceu_senha"] and not st.session_state["criar_usuario"]:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button("Entrar"):
                user = autenticar_usuario(email, senha)
                if user:
                    token = generate_token(
                        user_id=user[0], nome=user[1], perfil=user[4], status=user[5]
                    )
                    expire_time = datetime.now() + timedelta(minutes=120)
                    cookie_manager.set(
                        "session_token",
                        token,
                        expires_at=expire_time,
                        secure=False  # True em produção HTTPS
                    )
                    st.session_state["token"] = token
                    st.session_state["user_id"] = user[0]
                    st.session_state["user_name"] = user[1]
                    st.session_state["user_role"] = user[4]
                    st.session_state["pagina"] = "Painel do Participante"
                    st.success(f"Bem-vindo, {user[1]}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
        with col2:
            if st.button("Esqueceu a senha?"):
                st.session_state["esqueceu_senha"] = True
        with col3:
            if st.button("Criar usuário"):
                st.session_state["criar_usuario"] = True

        st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: flex-end; margin-top: 32px;">
                <a href="https://m.do.co/c/ed76b371e0d7" target="_blank">
                    <img src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg" alt="DigitalOcean Referral" width="80">
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    elif st.session_state["esqueceu_senha"]:
        st.header("Recuperar senha")
        rec_email = st.text_input("Seu email para recuperação")
        if st.button("Enviar email de recuperação"):
            ok, result = redefinir_senha_usuario(rec_email)
            if ok:
                nome, nova_senha = result
                enviar_email_recuperacao_senha(rec_email, nome, nova_senha)
                st.success("Senha temporária gerada e enviada! Verifique seu e-mail.")
            else:
                st.error(result)
        if st.button("Voltar"):
            st.session_state["esqueceu_senha"] = False

    elif st.session_state["criar_usuario"]:
        st.header("Criar novo usuário")
        nome = st.text_input("Nome completo")
        email_novo = st.text_input("Email para cadastro")
        senha_novo = st.text_input("Senha", type="password")
        senha_conf = st.text_input("Confirme a senha", type="password")
        if st.button("Registrar"):
            if not nome or not email_novo or not senha_novo or not senha_conf:
                st.warning("Preencha todos os campos.")
            elif senha_novo != senha_conf:
                st.error("As senhas não coincidem.")
            elif get_user_by_email(email_novo):
                st.error("Já existe um usuário com este email.")
            else:
                ok = cadastrar_usuario(nome, email_novo, senha_novo)
                if ok:
                    st.success("Usuário criado com sucesso! Faça login.")
                    st.session_state["criar_usuario"] = False
                else:
                    st.error("Erro ao cadastrar o usuário. Tente novamente.")
        if st.button("Voltar "):
            st.session_state["criar_usuario"] = False

if __name__ == '__main__':
    login_view()
