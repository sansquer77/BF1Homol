import jwt
from datetime import datetime, timedelta, timezone
import os
import logging
import importlib
import hashlib
import secrets

try:
    stx = importlib.import_module("extra_streamlit_components")
except ImportError:
    stx = None

# Funções de hash/check de senha - importadas de db_utils para evitar duplicação
# Re-exportadas aqui para manter compatibilidade com módulos que importam de auth_service
from db.db_utils import db_connect, get_table_columns, hash_password, check_password

# Exportar explicitamente para manter compatibilidade
__all__ = ['hash_password', 'check_password', 'autenticar_usuario', 'generate_token', 
           'decode_token', 'create_token', 'cadastrar_usuario', 'get_user_by_email',
           'get_user_by_id', 'set_auth_cookies', 'clear_auth_cookies', 'get_auth_cookie_token',
           'redefinir_senha_usuario', 'redefinir_senha_com_token']

logger = logging.getLogger(__name__)

JWT_MIN_SECRET_BYTES = 32
RESET_TOKEN_EXP_MINUTES = int(os.environ.get("RESET_TOKEN_EXP_MINUTES", "30"))
_JWT_SECRET_LOGGED = False

_COOKIE_MANAGER_INSTANCE = None
_COOKIE_MANAGER_KEY = "bf1_auth_cookie_manager"
_FALLBACK_COOKIE_STORE: dict[str, str] = {}


def _get_session_store() -> dict:
    """Return Streamlit session_state when available, else module-local fallback store."""
    try:
        st_mod = importlib.import_module("streamlit")
        return st_mod.session_state
    except Exception:
        return _FALLBACK_COOKIE_STORE


class _FallbackCookieManager:
    """Fallback simples quando extra_streamlit_components não está instalado."""

    def set(self, key, value, expires_at=None, options=None):
        store = _get_session_store()
        store[f"cookie_{key}"] = value

    def delete(self, key):
        store = _get_session_store()
        store.pop(f"cookie_{key}", None)

    def get_all(self):
        # Keep API compatible with CookieManager.get_all().
        store = _get_session_store()
        return {
            k.replace("cookie_", "", 1): v
            for k, v in store.items()
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
# JWT_SECRET DEVE ser configurado via variável de ambiente
# Em produção, NUNCA usar fallback hardcoded

def _get_jwt_secret() -> str:
    """Obtém JWT_SECRET de forma segura. Lança erro se não configurado em produção."""
    global _JWT_SECRET_LOGGED
    secret_from_env = (os.environ.get("JWT_SECRET") or "").strip()

    # Ambiente DigitalOcean/App Platform usa variável de ambiente.
    env_len = len(secret_from_env.encode("utf-8")) if secret_from_env else 0

    secret = ""
    secret_source = "none"
    if secret_from_env and env_len >= JWT_MIN_SECRET_BYTES:
        secret = secret_from_env
        secret_source = "env"
    elif secret_from_env:
        secret = secret_from_env
        secret_source = "env"
    
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
                "Configure a variável de ambiente JWT_SECRET."
            )
        
        # 🔴 ERRO CRÍTICO - JWT_SECRET SEMPRE OBRIGATÓRIO
        logger.critical("🔴 JWT_SECRET não configurado - SEGURANÇA COMPROMETIDA!")
        raise RuntimeError(
            "ERRO CRÍTICO DE SEGURANÇA: JWT_SECRET não está configurado.\n"
            "Este é um valor obrigatório que deve ser definido ANTES do deployment.\n"
            "Configure em: Digital Ocean > App Settings > Environment Variables > JWT_SECRET"
        )

    secret_len_bytes = len(secret.encode("utf-8"))
    if not _JWT_SECRET_LOGGED:
        logger.info(f"JWT_SECRET carregado de {secret_source} com {secret_len_bytes} bytes")
        _JWT_SECRET_LOGGED = True
    if secret_len_bytes < JWT_MIN_SECRET_BYTES:
        msg = (
            "ERRO CRÍTICO DE SEGURANÇA: JWT_SECRET muito curto para HS256. "
            f"Atual: {secret_len_bytes} bytes, mínimo recomendado: {JWT_MIN_SECRET_BYTES} bytes. "
            "Gere um segredo forte (>=32 bytes) e atualize em Digital Ocean > App Settings > Environment Variables > JWT_SECRET"
        )
        if is_production:
            logger.critical(msg)
            raise RuntimeError(msg)

        logger.warning(msg)
    return secret

# Validação no startup para falhar cedo em configuração inválida.
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
    jwt_secret = _get_jwt_secret()
    payload = {
        "user_id": user_id,
        "nome": nome,
        "perfil": perfil,
        "status": status,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES)
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_token(token: str):
    """Decodifica e valida um JWT; retorna o payload, ou None se inválido/expirado."""
    try:
        jwt_secret = _get_jwt_secret()
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
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
        cookie_manager.delete("session_token")
    except KeyError:
        # extra_streamlit_components can raise KeyError when cookie is absent.
        pass
    except Exception as exc:
        logger.warning("Falha ao limpar cookie de sessao: %s", exc)


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


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _ensure_password_reset_table(conn) -> None:
    c = conn.cursor()
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            email TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_prt_email_used ON password_reset_tokens(email, used_at)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_prt_expires_at ON password_reset_tokens(expires_at)"
    )

def redefinir_senha_usuario(email: str):
    usuario = get_user_by_email(email)
    if not usuario:
        return False, "Usuário não encontrado."

    reset_token = secrets.token_urlsafe(24)
    token_hash = _hash_reset_token(reset_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXP_MINUTES)

    with db_connect() as conn:
        _ensure_password_reset_table(conn)
        c = conn.cursor()
        # Invalida tokens pendentes anteriores para o mesmo email.
        c.execute(
            "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE email=? AND used_at IS NULL",
            (email,),
        )
        c.execute(
            "INSERT INTO password_reset_tokens (email, token_hash, expires_at) VALUES (?, ?, ?)",
            (email, token_hash, expires_at),
        )
        conn.commit()

    return True, (usuario[1], reset_token, RESET_TOKEN_EXP_MINUTES)


def redefinir_senha_com_token(email: str, token: str, nova_senha: str):
    token_hash = _hash_reset_token(token)
    now_utc = datetime.now(timezone.utc)

    with db_connect() as conn:
        _ensure_password_reset_table(conn)
        c = conn.cursor()
        c.execute(
            """
            SELECT id
            FROM password_reset_tokens
            WHERE email = ?
              AND token_hash = ?
              AND used_at IS NULL
              AND expires_at > ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (email, token_hash, now_utc),
        )
        token_row = c.fetchone()
        if not token_row:
            return False, "Token inválido ou expirado."

        senha_hash = hash_password(nova_senha)
        cols = get_table_columns(conn, 'usuarios')
        if 'must_change_password' in cols:
            c.execute(
                "UPDATE usuarios SET senha_hash=?, must_change_password=0 WHERE email=?",
                (senha_hash, email),
            )
        else:
            c.execute("UPDATE usuarios SET senha_hash=? WHERE email=?", (senha_hash, email))

        c.execute(
            "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=?",
            (token_row[0],),
        )
        conn.commit()

    return True, "Senha redefinida com sucesso."

# --- CRIAÇÃO AUTOMÁTICA DO MASTER ---
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
