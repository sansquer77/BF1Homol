import os
import jwt
import bcrypt
import logging
import re
from datetime import datetime, timedelta
from db.db_utils import db_connect, get_table_columns, hash_password
from db.connection_pool import get_pool

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get('JWT_SECRET', 'bf1-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '480'))

# --- Limite de tentativas de login ---
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def generate_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Gera um JWT para o usuário autenticado."""
    payload = {
        'user_id': user_id,
        'nome': nome,
        'perfil': perfil,
        'status': status,
        'exp': datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict | None:
    """Verifica e decodifica um JWT. Retorna payload ou None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Token inválido: %s", e)
        return None

def _is_locked_out(email: str) -> bool:
    """Verifica se o email está bloqueado por excesso de tentativas."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'login_attempts')
            if not cols:
                return False
            cutoff = (datetime.utcnow() - timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            c.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE email = %s AND attempted_at > %s",
                (email, cutoff)
            )
            row = c.fetchone()
            count = row[0] if row else 0
            return count >= MAX_LOGIN_ATTEMPTS
    except Exception as e:
        logger.warning("Erro ao verificar lockout: %s", e)
        return False

def _record_failed_attempt(email: str) -> None:
    """Registra uma tentativa de login falha."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'login_attempts')
            if not cols:
                return
            c.execute(
                "INSERT INTO login_attempts (email, attempted_at) VALUES (%s, %s)",
                (email, datetime.utcnow().isoformat())
            )
            conn.commit()
    except Exception as e:
        logger.warning("Erro ao registrar tentativa falha: %s", e)

def _clear_failed_attempts(email: str) -> None:
    """Remove tentativas de login falhas após login bem-sucedido."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'login_attempts')
            if not cols:
                return
            c.execute("DELETE FROM login_attempts WHERE email = %s", (email,))
            conn.commit()
    except Exception as e:
        logger.warning("Erro ao limpar tentativas: %s", e)

def login(email: str, senha: str) -> tuple[bool, str | dict]:
    """
    Autentica usuário e retorna (True, dados_usuario) ou (False, mensagem_erro).
    """
    if not email or not senha:
        return False, "Email e senha são obrigatórios"

    email = email.strip().lower()

    if _is_locked_out(email):
        return False, f"Conta bloqueada por excesso de tentativas. Tente novamente em {LOCKOUT_MINUTES} minutos."

    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute("SELECT id, nome, email, senha_hash, perfil, status FROM usuarios WHERE email=%s",
                      (email,))
            usuario = c.fetchone()

        if not usuario:
            _record_failed_attempt(email)
            return False, "Email ou senha incorretos"

        user_id, nome, user_email, senha_hash, perfil, status = (
            usuario['id'], usuario['nome'], usuario['email'],
            usuario['senha_hash'], usuario['perfil'], usuario['status']
        )

        if status != 'Ativo':
            return False, "Usuário inativo. Entre em contato com o administrador."

        if not bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8')):
            _record_failed_attempt(email)
            return False, "Email ou senha incorretos"

        _clear_failed_attempts(email)

        token = generate_token(user_id, nome, perfil, status)
        return True, {
            'token': token,
            'user_id': user_id,
            'nome': nome,
            'email': user_email,
            'perfil': perfil,
            'status': status
        }

    except Exception as e:
        logger.exception("Erro no login: %s", e)
        return False, "Erro interno do servidor"

def get_current_user(token: str) -> dict | None:
    """Retorna dados completos do usuário a partir do token JWT."""
    payload = verify_token(token)
    if not payload:
        return None

    user_id = payload.get('user_id')
    if not user_id:
        return None

    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'usuarios')
            if 'must_change_password' in cols:
                c.execute(
                    "SELECT id, nome, email, senha_hash, perfil, status, faltas FROM usuarios WHERE email=%s",
                    (payload.get('email') or '',)
                )
            else:
                c.execute(
                    "SELECT id, nome, email, perfil, status, faltas FROM usuarios WHERE id=%s",
                    (user_id,)
                )
            usuario = c.fetchone()

        if not usuario:
            return None

        return {
            'user_id': usuario['id'] if 'id' in usuario.keys() else usuario[0],
            'nome': usuario['nome'] if 'nome' in usuario.keys() else usuario[1],
            'perfil': usuario['perfil'] if 'perfil' in usuario.keys() else usuario[3],
            'status': usuario['status'] if 'status' in usuario.keys() else usuario[4],
        }
    except Exception as e:
        logger.exception("Erro ao buscar usuário: %s", e)
        return None

def reset_password(email: str) -> tuple[bool, tuple[str, str] | str]:
    """Reseta a senha do usuário e gera uma nova senha aleatória."""
    import secrets
    import string

    email = email.strip().lower()

    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, nome, email, senha_hash, perfil, status, faltas FROM usuarios WHERE email=%s",
                (email,)
            )
            usuario = c.fetchone()

        if not usuario:
            return False, "Email não encontrado"

        alphabet = string.ascii_letters + string.digits
        nova_senha = ''.join(secrets.choice(alphabet) for _ in range(12))
        senha_hash = hash_password(nova_senha)

        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'usuarios')
            if 'must_change_password' in cols:
                c.execute(
                    "UPDATE usuarios SET senha_hash=%s, must_change_password=1 WHERE email=%s",
                    (senha_hash, email)
                )
            else:
                c.execute("UPDATE usuarios SET senha_hash=%s WHERE email=%s", (senha_hash, email))
            conn.commit()
        return True, (usuario['nome'] if hasattr(usuario, 'keys') else usuario[1], nova_senha)

    except Exception as e:
        logger.exception("Erro ao resetar senha: %s", e)
        return False, "Erro interno do servidor"

# --- CRIaÇÃO AUTOMÁTICA DO MASTER ---
def _get_secret_value(*keys):
    """Busca valor em múltiplas chaves (maiúscula/minúscula) no os.environ."""
    for key in keys:
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
        c.execute('SELECT COUNT(*) FROM usuarios WHERE perfil = %s', ('master',))
        existe = c.fetchone()[0] > 0
        if not existe:
            senha_hash = hash_password(senha)
            c.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, perfil, status, faltas) VALUES (%s, %s, %s, %s, %s, 0)',
                (nome, email, senha_hash, 'master', 'Ativo')
            )
            conn.commit()

# Alias para compatibilidade
def create_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Alias para generate_token - cria um JWT para o usuário autenticado."""
    return generate_token(user_id, nome, perfil, status)

def decode_token(token: str) -> dict | None:
    """Alias para verify_token - verifica e decodifica um JWT."""
    return verify_token(token)

def logout(token: str) -> bool:
    """Invalida o token do usuário (implementação client-side)."""
    logger.info("Logout realizado para token: %s...", token[:20] if token else 'N/A')
    return True
