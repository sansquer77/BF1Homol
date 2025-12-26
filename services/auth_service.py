import jwt
from datetime import datetime, timedelta, timezone
import streamlit as st
import extra_streamlit_components as stx
import os
import logging

# Funções de hash/check de senha - importadas de db_utils para evitar duplicação
# Re-exportadas aqui para manter compatibilidade com módulos que importam de auth_service
from db.db_utils import db_connect, hash_password, check_password

# Exportar explicitamente para manter compatibilidade
__all__ = ['hash_password', 'check_password', 'autenticar_usuario', 'generate_token', 
           'decode_token', 'create_token', 'cadastrar_usuario', 'get_user_by_email',
           'get_user_by_id', 'set_auth_cookies', 'clear_auth_cookies']

logger = logging.getLogger(__name__)

# ============ CONFIGURAÇÃO JWT ============
# JWT_SECRET DEVE ser configurado via st.secrets ou variável de ambiente
# Em produção, NUNCA usar fallback hardcoded

def _get_jwt_secret() -> str:
    """Obtém JWT_SECRET de forma segura. Lança erro se não configurado em produção."""
    secret = None
    
    # Tentar obter de st.secrets primeiro
    try:
        secret = st.secrets.get("JWT_SECRET")
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    
    # Fallback para variável de ambiente
    if not secret:
        secret = os.environ.get("JWT_SECRET")
    
    # Verificar se está em ambiente de produção (Digital Ocean / Streamlit Cloud)
    is_production = (
        os.environ.get("STREAMLIT_SHARING") or 
        os.environ.get("DIGITALOCEAN_APP_PLATFORM") or
        os.environ.get("PRODUCTION") == "true"
    )
    
    if not secret:
        if is_production:
            logger.critical("JWT_SECRET não configurado em ambiente de produção!")
            raise RuntimeError(
                "ERRO CRÍTICO DE SEGURANÇA: JWT_SECRET não está configurado. "
                "Configure a variável de ambiente JWT_SECRET ou adicione em st.secrets."
            )
        else:
            # Apenas em desenvolvimento local - com aviso
            logger.warning(
                "⚠️  JWT_SECRET não configurado - usando chave de desenvolvimento. "
                "NÃO USE EM PRODUÇÃO!"
            )
            secret = "DEV_ONLY_bf1dev_secret_key_2025_NOT_FOR_PRODUCTION"
    
    return secret

JWT_SECRET = _get_jwt_secret()
JWT_EXP_MINUTES = 120

# --- AUTENTICAÇÃO ---
def autenticar_usuario(email: str, senha: str):
    """Retorna o usuário autenticado (tupla de dados) ou None."""
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id, nome, email, senha_hash, perfil, status FROM usuarios WHERE email=?", (email,))
        user = c.fetchone()
    if user and check_password(senha, user[3]):
        return user
    return None

# --- GERAÇÃO E DECODIFICAÇÃO DE TOKEN JWT ---
def generate_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Gera um JWT para o usuário autenticado, incluindo o nome."""
    payload = {
        "user_id": user_id,
        "nome": nome,
        "perfil": perfil,
        "status": status,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_token(token: str):
    """Decodifica e valida um JWT; retorna o payload, ou None se inválido/expirado."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except Exception:
        return None

# --- REGISTRO DE USUÁRIO ---
def cadastrar_usuario(nome: str, email: str, senha: str, perfil="participante", status="Ativo") -> bool:
    """Cria novo usuário, garantindo unicidade de email."""
    try:
        senha_hash = hash_password(senha)
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, perfil, status, faltas) VALUES (?, ?, ?, ?, ?, ?)',
                (nome, email, senha_hash, perfil, status, 0)
            )
            conn.commit()
        return True
    except Exception:
        return False

# --- BUSCA DE USUÁRIOS ---
def get_user_by_email(email: str):
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, nome, email, senha_hash, perfil, status, faltas FROM usuarios WHERE email=?",
            (email,)
        )
        user = c.fetchone()
    return user

def get_user_by_id(user_id):
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, nome, email, perfil, status, faltas FROM usuarios WHERE id=?",
            (user_id,)
        )
        user = c.fetchone()
    return user

# --- GESTÃO DE COOKIES (para login) ---
def set_auth_cookies(token, expires_minutes=JWT_EXP_MINUTES):
    """Salva o token JWT em cookie para restaurar a sessão."""
    cookie_manager = stx.CookieManager()
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    cookie_manager.set(
        "session_token",
        token,
        expires_at=expires_at
    )

def clear_auth_cookies():
    cookie_manager = stx.CookieManager()
    cookie_manager.delete("session_token")

# --- RECUPERAÇÃO DE SENHA SEGURA ---
import random
import string
def gerar_senha_temporaria(tamanho=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=tamanho))

def redefinir_senha_usuario(email: str):
    usuario = get_user_by_email(email)
    if not usuario:
        return False, "Usuário não encontrado."
    nova_senha = gerar_senha_temporaria()
    senha_hash = hash_password(nova_senha)
    # Atualiza a senha no banco
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("UPDATE usuarios SET senha_hash=? WHERE email=?", (senha_hash, email))
        conn.commit()
    return True, (usuario[1], nova_senha)  # nome, nova_senha

# --- CRIAÇÃO AUTOMÁTICA DO MASTER ---
def criar_master_se_nao_existir():
    nome = st.secrets.get('usuario_master') or os.environ.get('usuario_master')
    email = st.secrets.get('email_master') or os.environ.get('email_master')
    senha = st.secrets.get('senha_master') or os.environ.get('senha_master')
    if not (nome and email and senha):
        return
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM usuarios WHERE perfil="master"')
        existe = c.fetchone()[0] > 0
        if not existe:
            senha_hash = hash_password(senha)
            c.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, perfil, status, faltas) VALUES (?, ?, ?, "master", "Ativo", 0)',
                (nome, email, senha_hash)
            )
            conn.commit()

# Alias para compatibilidade
def create_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Alias para generate_token - cria um JWT para o usuário autenticado."""
    return generate_token(user_id, nome, perfil, status)
