"""
Sistema de Login - BF1Dev 3.0
Melhorias:
- Rate limiting para segurança
- Bcrypt para verificação de senha
- Feedback de tentativas de login
- JWT Token generation
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from db import (
    db_connect,
    check_password,
    get_user_by_email,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION
)
from services.auth_service import create_token

logger = logging.getLogger(__name__)

# ============ RATE LIMITING ============

def registrar_tentativa_login(email: str, sucesso: bool, ip_address: str = "LOCAL"):
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
            INSERT INTO login_attempts (email, sucesso, ip_address)
            VALUES (?, ?, ?)
        ''', (email, sucesso, ip_address))
        conn.commit()


def obter_tentativas_recentes(email: str) -> tuple[int, bool]:
    """
    Obtém tentativas de login recentes
    
    Returns:
        (numero_tentativas, usuario_bloqueado)
    """
    with db_connect() as conn:
        cursor = conn.cursor()
        
        # Buscar tentativas dos últimos 15 minutos
        tempo_limite = datetime.now() - timedelta(seconds=LOCKOUT_DURATION)
        
        cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN sucesso=0 THEN 1 ELSE 0 END) as falhas
            FROM login_attempts
            WHERE email = ? AND tentativa_em > ?
        ''', (email, tempo_limite))
        
        resultado = cursor.fetchone()
        total = resultado[0] if resultado else 0
        falhas = resultado[1] if resultado and resultado[1] else 0
        
        # Bloqueado se tiver mais que MAX_LOGIN_ATTEMPTS falhas
        bloqueado = falhas >= MAX_LOGIN_ATTEMPTS
        
        return falhas, bloqueado


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
        st.markdown("# 🏁 BF1Dev - Bolão de F1")
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
                use_container_width=True,
                type="primary"
            )
        
        # ========== PROCESSAMENTO DO LOGIN ==========
        if submit_button:
            if not email or not senha:
                st.error("❌ Por favor, preencha email e senha")
                logger.warning(f"Tentativa de login com campos vazios")
                return
            
            # Verificar rate limiting
            falhas, bloqueado = obter_tentativas_recentes(email)
            
            if bloqueado:
                tempo_bloqueio = LOCKOUT_DURATION // 60  # Converter para minutos
                st.error(
                    f"🔒 **Conta temporariamente bloqueada**\n\n"
                    f"Muitas tentativas de login falhadas. "
                    f"Tente novamente em {tempo_bloqueio} minutos."
                )
                logger.warning(f"Tentativa de login bloqueada por rate limiting: {email}")
                registrar_tentativa_login(email, False)
                return
            
            # Buscar usuário
            usuario = get_user_by_email(email)
            
            if not usuario:
                st.error("❌ Email ou senha incorretos")
                logger.warning(f"Tentativa de login com email inexistente: {email}")
                registrar_tentativa_login(email, False)
                return
            
            # Verificar status
            if usuario['status'] != 'Ativo':
                st.error(f"❌ Usuário inativo. Status: {usuario['status']}")
                logger.warning(f"Tentativa de login com usuário inativo: {email}")
                registrar_tentativa_login(email, False)
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
                registrar_tentativa_login(email, False)
                return
            
            # ========== LOGIN SUCESSO ==========
            try:
                # Gerar JWT Token
                token = create_token(
                    user_id=usuario['id'],
                    nome=usuario['nome'],
                    perfil=usuario['perfil'],
                    status=usuario.get('status', 'Ativo')
                )
                
                # Armazenar no session_state
                st.session_state['token'] = token
                st.session_state['user_id'] = usuario['id']
                st.session_state['user_email'] = usuario['email']
                st.session_state['user_nome'] = usuario['nome']
                st.session_state['user_role'] = usuario['perfil']
                st.session_state['pagina'] = "Painel do Participante"
                
                # Registrar sucesso
                registrar_tentativa_login(email, True)
                
                logger.info(f"✓ Login bem-sucedido: {email} ({usuario['perfil']})")
                
                st.success(f"✅ Bem-vindo, {usuario['nome']}!")
                st.balloons()
                
                # Rerun para carregar próxima página
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar token de autenticação.")