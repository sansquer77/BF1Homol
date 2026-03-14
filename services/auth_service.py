import jwt
from datetime import datetime, timedelta, timezone
import streamlit as st
import os
import logging
import importlib

try:
    stx = importlib.import_module("extra_streamlit_components")
except ImportError:
    stx = None

# Funções de hash/check de senha - importadas de db_utils para evitar duplicação
# Re-exportadas aqui para manter compatibilidade com módulos que importam de auth_service
from db.db_utils import db_connect, hash_password, check_password

# Exportar explicitamente para manter compatibilidade
__all__ = ['hash_password', 'check_password', 'autenticar_usuario', 'generate_token', 
           'decode_token', 'create_token', 'cadastrar_usuario', 'get_user_by_email',
           'get_user_by_id', 'set_auth_cookies', 'clear_auth_cookies', 'get_auth_cookie_token']

logger = logging.getLogger(__name__)

MIN_JWT_SECRET_BYTES = 32

_COOKIE_MANAGER_INSTANCE = None
_COOKIE_MANAGER_KEY = "bf1_auth_cookie_manager"


class _FallbackCookieManager:
    """Fallback simples quando extra_streamlit_components não está instalado."""

    def set(self, key, value, expires_at=None, options=None):
        st.session_state[f"cookie_{key}"] = value

    def delete(self, key):
        st.session_state.pop(f"cookie_{key}", None)

    def get_all(self):
        # Keep API compatible with CookieManager.get_all().
        return {
            k.replace("cookie_", "", 1): v
            for k, v in st.session_state.items()
            if isinstance(k, str) and k.startswith("cookie_")
        }


def _get_cookie_manager():
    global _COOKIE_MANAGER_INSTANCE
    if _COOKIE_MANAGER_INSTANCE is not None:
        return _COOKIE_MANAGER_INSTANCE

    if stx is not None:
        _COOKIE_MANAGER_INSTANCE = stx.CookieManager(key=_COOKIE_MANAGER_KEY)
    else:
        _COOKIE_MANAGER_INSTANCE = _FallbackCookieManager()
    return _COOKIE_MANAGER_INSTANCE

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
        os.environ.get("PRODUCTION", "").lower() == "true"
    )
    
    if not secret:
        if is_production:
            logger.critical("JWT_SECRET não configurado em ambiente de produção!")
            raise RuntimeError(
                "ERRO CRÍTICO DE SEGURANÇA: JWT_SECRET não está configurado. "
                "Configure a variável de ambiente JWT_SECRET ou adicione em st.secrets."
            )
        
        # 🔴 ERRO CRÍTICO - JWT_SECRET SEMPRE OBRIGATÓRIO
        logger.critical("🔴 JWT_SECRET não configurado - SEGURANÇA COMPROMETIDA!")
        raise RuntimeError(
            "ERRO CRÍTICO DE SEGURANÇA: JWT_SECRET não está configurado.\n"
            "Este é um valor obrigatório que deve ser definido ANTES do deployment.\n"
            "Configure em: Digital Ocean > App Settings > Environment Variables > JWT_SECRET"
        )

    secret_bytes = secret.encode("utf-8")
    allow_weak_secret = os.environ.get("JWT_ALLOW_WEAK_SECRET", "").lower() == "true"
    if len(secret_bytes) < MIN_JWT_SECRET_BYTES:
        message = (
            f"JWT_SECRET inseguro: {len(secret_bytes)} bytes. "
            f"Mínimo recomendado para HS256: {MIN_JWT_SECRET_BYTES} bytes."
        )
        if is_production or not allow_weak_secret:
            logger.critical(message)
            raise RuntimeError(
                message + " Defina um JWT_SECRET forte no ambiente."
            )

        logger.warning(
            "%s Continuando apenas por JWT_ALLOW_WEAK_SECRET=true (somente dev).",
            message,
        )

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
            user_id = c.lastrowid
            conn.commit()
        try:
            if isinstance(user_id, int):
                from db.db_utils import registrar_historico_status_usuario
                registrar_historico_status_usuario(
                    user_id,
                    status,
                    alterado_por=None,
                    motivo="cadastrar_usuario"
                )
        except Exception:
            pass
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
    cookie_manager = _get_cookie_manager()
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    try:
        cookie_manager.set(
            "session_token",
            token,
            expires_at=expires_at,
            options={
                "path": "/",
                "secure": True,
                "httponly": True,
                "samesite": "Lax"
            }
        )
    except TypeError:
        cookie_manager.set(
            "session_token",
            token,
            expires_at=expires_at
        )

def clear_auth_cookies():
    cookie_manager = _get_cookie_manager()
    try:
        cookies = cookie_manager.get_all()
        if isinstance(cookies, dict) and "session_token" not in cookies:
            return
    except Exception:
        # If cookie listing fails, still attempt deletion below.
        pass

    try:
        cookie_manager.delete("session_token")
    except KeyError:
        # extra_streamlit_components can raise KeyError when cookie is absent.
        pass


def get_auth_cookie_token():
    """Retorna token de sessão salvo em cookie, quando disponível."""
    cookie_manager = _get_cookie_manager()
    try:
        cookies = cookie_manager.get_all()
        if isinstance(cookies, dict):
            token = cookies.get("session_token")
            if token:
                return str(token)
    except Exception:
        return None
    return None

# --- RECUPERAÇÃO DE SENHA SEGURA ---
import secrets
import string
def gerar_senha_temporaria(tamanho=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(tamanho))

def redefinir_senha_usuario(email: str):
    usuario = get_user_by_email(email)
    if not usuario:
        return False, "Usuário não encontrado."
    nova_senha = gerar_senha_temporaria()
    senha_hash = hash_password(nova_senha)
    # Atualiza a senha no banco
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('usuarios')")
        cols = [r[1] for r in c.fetchall()]
        if 'must_change_password' in cols:
            c.execute(
                "UPDATE usuarios SET senha_hash=?, must_change_password=1 WHERE email=?",
                (senha_hash, email)
            )
        else:
            c.execute("UPDATE usuarios SET senha_hash=? WHERE email=?", (senha_hash, email))
        conn.commit()
    return True, (usuario[1], nova_senha)  # nome, nova_senha

# --- CRIAÇÃO AUTOMÁTICA DO MASTER ---
def _get_secret_value(*keys):
    """Busca valor em múltiplas chaves (maiúscula/minúscula) em st.secrets e os.environ"""
    for key in keys:
        try:
            value = st.secrets.get(key)
            if value:
                return value
        except:
            pass
        value = os.environ.get(key)
        if value:
            return value
    return None

def criar_master_se_nao_existir():
    nome = _get_secret_value('USUARIO_MASTER', 'usuario_master')
    email = _get_secret_value('EMAIL_MASTER', 'email_master')
    senha = _get_secret_value('SENHA_MASTER', 'senha_master')
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
