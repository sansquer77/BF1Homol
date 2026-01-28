import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
import streamlit as st
import extra_streamlit_components as stx
from db.db_utils import db_connect
import os

JWT_SECRET = st.secrets["JWT_SECRET"] or os.environ.get("JWT_SECRET")
JWT_EXP_MINUTES = 120

# --- HASH E CHECK DE SENHA ---
def hash_password(password: str) -> str:
    """Gera um hash bcrypt para a senha fornecida."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")

def check_password(password: str, hashed: str) -> bool:
    """Valida uma senha em texto puro contra um hash bcrypt."""
    if isinstance(hashed, str):
        hashed = hashed.encode()
    return bcrypt.checkpw(password.encode(), hashed)

# --- AUTENTICAÇÃO ---
def autenticar_usuario(email: str, senha: str):
    """Retorna o usuário autenticado (tupla de dados) ou None."""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT id, nome, email, senha_hash, perfil, status FROM usuarios WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
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
    conn = db_connect()
    c = conn.cursor()
    try:
        senha_hash = hash_password(senha)
        c.execute(
            'INSERT INTO usuarios (nome, email, senha_hash, perfil, status, faltas) VALUES (?, ?, ?, ?, ?, ?)',
            (nome, email, senha_hash, perfil, status, 0)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

# --- BUSCA DE USUÁRIOS ---
def get_user_by_email(email: str):
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "SELECT id, nome, email, senha_hash, perfil, status, faltas FROM usuarios WHERE email=?",
        (email,)
    )
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "SELECT id, nome, email, perfil, status, faltas FROM usuarios WHERE id=?",
        (user_id,)
    )
    user = c.fetchone()
    conn.close()
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
    conn = db_connect()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET senha_hash=? WHERE email=?", (senha_hash, email))
    conn.commit()
    conn.close()
    return True, (usuario[1], nova_senha)  # nome, nova_senha

# --- CRIAÇÃO AUTOMÁTICA DO MASTER ---
def criar_master_se_nao_existir():
    nome = st.secrets.get('usuario_master') or os.environ.get('usuario_master')
    email = st.secrets.get('email_master') or os.environ.get('email_master')
    senha = st.secrets.get('senha_master') or os.environ.get('senha_master')
    if not (nome and email and senha):
        return
    conn = db_connect()
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
    conn.close()
