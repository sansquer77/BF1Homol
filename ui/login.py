"""
Sistema de Login - BF1 3.0
Melhorias:
- Rate limiting para segurança
- Bcrypt para verificação de senha
- Feedback de tentativas de login
- JWT Token generation
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from services.auth_service import redefinir_senha_usuario
from services.auth_service import set_auth_cookies
from services.email_service import enviar_email_recuperacao_senha
from utils.request_utils import get_client_ip
from utils.validators import validar_email
from db import (
    db_connect,
    check_password,
    get_user_by_email,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION,
    MAX_RESET_ATTEMPTS,
    RESET_LOCKOUT_DURATION
)
from services.auth_service import create_token

logger = logging.getLogger(__name__)

# ============ RATE LIMITING ============

def registrar_tentativa_login(email: str, sucesso: bool, ip_address: str = "LOCAL", action: str = "login"):
    """
    Registra tentativa de login para rate limiting
    
    Args:
        email: Email do usuário
        sucesso: True se login foi bem-sucedido
        ip_address: IP da requisição (para análise de segurança)
    """
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_attempts (email, sucesso, ip_address, action)
            VALUES (?, ?, ?, ?)
        ''', (email, sucesso, ip_address, action))
        conn.commit()


def obter_tentativas_recentes(
    email: str,
    ip_address: str,
    max_attempts: int = MAX_LOGIN_ATTEMPTS,
    lockout_seconds: int = LOCKOUT_DURATION,
    action: str = "login"
) -> tuple[int, int, bool]:
    """
    Obtém tentativas de login recentes
    
    Returns:
        (falhas_email, falhas_ip, usuario_bloqueado)
    """
    with db_connect() as conn:
        cursor = conn.cursor()
        
        # Buscar tentativas dos últimos 15 minutos
        tempo_limite = datetime.now() - timedelta(seconds=lockout_seconds)
        
        cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN sucesso IS NOT TRUE THEN 1 ELSE 0 END) as falhas
            FROM login_attempts
            WHERE email = ? AND tentativa_em > ? AND action = ?
        ''', (email, tempo_limite, action))
        
        resultado = cursor.fetchone()
        falhas = resultado[1] if resultado and resultado[1] else 0

        cursor.execute('''
            SELECT SUM(CASE WHEN sucesso IS NOT TRUE THEN 1 ELSE 0 END) as falhas_ip
            FROM login_attempts
            WHERE ip_address = ? AND tentativa_em > ? AND action = ?
        ''', (ip_address, tempo_limite, action))

        resultado_ip = cursor.fetchone()
        falhas_ip = resultado_ip[0] if resultado_ip and resultado_ip[0] else 0
        
        # Bloqueado se tiver mais que MAX_LOGIN_ATTEMPTS falhas
        # Limite por IP mais permissivo para reduzir falso positivo em redes compartilhadas.
        bloqueado = falhas >= max_attempts or falhas_ip >= (max_attempts * 3)
        
        return falhas, falhas_ip, bloqueado


def _classificar_motivo_bloqueio(
    falhas_email: int,
    falhas_ip: int,
    max_attempts: int,
) -> str:
    """Classifica motivo operacional do bloqueio sem alterar regra de negócio."""
    bloqueio_email = falhas_email >= max_attempts
    bloqueio_ip = falhas_ip >= (max_attempts * 3)
    if bloqueio_email and bloqueio_ip:
        return "email+ip"
    if bloqueio_email:
        return "email"
    if bloqueio_ip:
        return "ip"
    return "none"


def limpar_tentativas_antigas():
    """Remove registros de tentativas mais antigos que 24h"""
    with db_connect() as conn:
        cursor = conn.cursor()
        tempo_limite = datetime.now() - timedelta(hours=24)
        
        cursor.execute('''
            DELETE FROM login_attempts
            WHERE tentativa_em < ?
        ''', (tempo_limite,))
        
        conn.commit()


# ============ UI DE LOGIN ============

def login_view():
    """Interface de login com rate limiting e segurança"""
    
    # Limpar tentativas antigas periodicamente
    if 'login_cleanup_done' not in st.session_state:
        limpar_tentativas_antigas()
        st.session_state['login_cleanup_done'] = True
    
    # ========== LAYOUT ==========
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🏁 BF1 - Bolão de F1")
        st.markdown("### Sistema de Apostas e Ranking")
        st.markdown("---")
        
        # ========== FORMULÁRIO ==========
        with st.form("login_form", clear_on_submit=False):
            st.subheader("Faça Login")
            
            email = st.text_input(
                "📧 Email",
                placeholder="seu@email.com",
                help="Email registrado no sistema"
            )
            
            senha = st.text_input(
                "🔐 Senha",
                type="password",
                placeholder="Sua senha segura",
                help="Mínimo 8 caracteres"
            )
            
            submit_button = st.form_submit_button(
                "🚀 Entrar",
                width="stretch",
                type="primary"
            )
        
        # ========== PROCESSAMENTO DO LOGIN ==========
        if submit_button:
            if not email or not senha:
                st.error("❌ Por favor, preencha email e senha")
                logger.warning(f"Tentativa de login com campos vazios")
                return
            valido_email, _ = validar_email(email)
            if not valido_email:
                st.error("❌ Email inválido")
                logger.warning("Tentativa de login com email inválido")
                return
            
            # Verificar rate limiting
            client_ip = get_client_ip() or "LOCAL"
            falhas, falhas_ip, bloqueado = obter_tentativas_recentes(
                email,
                client_ip,
                MAX_LOGIN_ATTEMPTS,
                LOCKOUT_DURATION,
                "login",
            )
            
            if bloqueado:
                tempo_bloqueio = LOCKOUT_DURATION // 60  # Converter para minutos
                st.error(
                    f"🔒 **Conta temporariamente bloqueada**\n\n"
                    f"Muitas tentativas de login falhadas. "
                    f"Tente novamente em {tempo_bloqueio} minutos."
                )
                motivo = _classificar_motivo_bloqueio(falhas, falhas_ip, MAX_LOGIN_ATTEMPTS)
                logger.warning(
                    "[SECURITY_AUDIT] login_blocked email=%s ip=%s motivo=%s falhas_email=%d falhas_ip=%d limite_email=%d limite_ip=%d",
                    email,
                    client_ip,
                    motivo,
                    falhas,
                    falhas_ip,
                    MAX_LOGIN_ATTEMPTS,
                    MAX_LOGIN_ATTEMPTS * 3,
                )
                registrar_tentativa_login(email, False, ip_address=client_ip, action="login")
                return
            
            # Buscar usuário
            usuario = get_user_by_email(email)
            
            if not usuario:
                st.error("❌ Email ou senha incorretos")
                logger.warning(f"Tentativa de login com email inexistente: {email}")
                registrar_tentativa_login(email, False, ip_address=client_ip, action="login")
                return
            
            # Verificar status
            if usuario['status'] != 'Ativo':
                st.error(f"❌ Usuário inativo. Status: {usuario['status']}")
                logger.warning(f"Tentativa de login com usuário inativo: {email}")
                registrar_tentativa_login(email, False, ip_address=client_ip, action="login")
                return
            
            # Verificar senha com bcrypt
            if not check_password(senha, usuario['senha_hash']):
                tentativas_restantes = MAX_LOGIN_ATTEMPTS - falhas - 1
                
                if tentativas_restantes > 0:
                    st.warning(
                        f"⚠️  Email ou senha incorretos.\n"
                        f"Tentativas restantes: {tentativas_restantes}"
                    )
                else:
                    st.error(
                        f"🔒 Muitas tentativas falhadas. "
                        f"Conta bloqueada por {LOCKOUT_DURATION // 60} minutos."
                    )
                
                logger.warning(f"Falha de autenticação para: {email}")
                registrar_tentativa_login(email, False, ip_address=client_ip, action="login")
                return
            
            # ========== LOGIN SUCESSO ==========
            try:
                token = create_token(
                    user_id=usuario['id'],
                    nome=usuario['nome'],
                    perfil=usuario['perfil'],
                    status=usuario.get('status', 'Ativo')
                )
            except Exception as e:
                logger.exception("Falha ao criar token JWT no login: %s", e)
                st.error("❌ Erro ao gerar token de autenticação.")
                return

            # Armazenar no session_state
            st.session_state['token'] = token
            st.session_state['user_id'] = usuario['id']
            st.session_state['user_email'] = usuario['email']
            st.session_state['user_nome'] = usuario['nome']
            st.session_state['user_role'] = usuario['perfil']
            st.session_state['pagina'] = "Painel do Participante"
            st.session_state['force_password_change'] = bool(usuario.get('must_change_password', 0))

            try:
                set_auth_cookies(token)
            except Exception as cookie_error:
                # Não bloquear login por falha de persistência do cookie.
                logger.warning("Falha ao persistir cookie de sessao no login: %s", cookie_error)

            # Registrar sucesso
            registrar_tentativa_login(email, True, ip_address=client_ip, action="login")

            logger.info(f"✓ Login bem-sucedido: {email} ({usuario['perfil']})")

            st.success(f"✅ Bem-vindo, {usuario['nome']}!")
            st.balloons()

            # Rerun para carregar próxima página
            st.rerun()

        # ========== ESQUECI A SENHA ==========
        with st.expander("Esqueci a senha"):
            st.write("Informe seu email para receber uma senha temporária.")
            with st.form("forgot_password_form", clear_on_submit=True):
                email_reset = st.text_input("📧 Email", placeholder="seu@email.com", key="reset_email")
                reset_submit = st.form_submit_button("Enviar senha temporária", width="stretch")

            if reset_submit:
                if not email_reset:
                    st.error("❌ Informe o email.")
                else:
                    valido, _ = validar_email(email_reset)
                    if not valido:
                        st.error("❌ Email inválido.")
                        return
                    reset_ip = get_client_ip() or "LOCAL"
                    falhas_email_reset, falhas_ip_reset, bloqueado = obter_tentativas_recentes(
                        email_reset,
                        reset_ip,
                        MAX_RESET_ATTEMPTS,
                        RESET_LOCKOUT_DURATION,
                        "password_reset"
                    )
                    if bloqueado:
                        motivo_reset = _classificar_motivo_bloqueio(
                            falhas_email_reset,
                            falhas_ip_reset,
                            MAX_RESET_ATTEMPTS,
                        )
                        logger.warning(
                            "[SECURITY_AUDIT] password_reset_blocked email=%s ip=%s motivo=%s falhas_email=%d falhas_ip=%d limite_email=%d limite_ip=%d",
                            email_reset,
                            reset_ip,
                            motivo_reset,
                            falhas_email_reset,
                            falhas_ip_reset,
                            MAX_RESET_ATTEMPTS,
                            MAX_RESET_ATTEMPTS * 3,
                        )
                        st.info("Se o email estiver cadastrado, você receberá uma senha temporária em instantes.")
                        registrar_tentativa_login(email_reset, False, ip_address=reset_ip, action="password_reset")
                    else:
                        ok, payload = redefinir_senha_usuario(email_reset)
                        if ok:
                            nome_usuario, nova_senha = payload
                            try:
                                enviar_email_recuperacao_senha(email_reset, nome_usuario, nova_senha)
                            except Exception as e:
                                logger.warning(f"Falha ao enviar email de recuperação para {email_reset}: {e}")
                        # Resposta genérica para evitar enumeração
                        st.info("Se o email estiver cadastrado, você receberá uma senha temporária em instantes.")
                        registrar_tentativa_login(email_reset, False, ip_address=reset_ip, action="password_reset")
