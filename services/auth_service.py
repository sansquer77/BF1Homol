import jwt
from datetime import datetime, timedelta, timezone
import os
import logging
import importlib
import hashlib
import secrets
import hmac
import uuid

try:
    stx = importlib.import_module("extra_streamlit_components")
except ImportError:
    stx = None

# Funções de auth/usuário importadas dos módulos focados de dados.
from db.db_schema import db_connect, get_table_columns
from db.repo_users import hash_password, check_password, get_user_by_id
from utils.cache_utils import clear_data_cache
from utils.security_utils import normalize_email_identifier

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


def _get_usuarios_password_column(conn) -> str:
    """Resolve a coluna de senha da tabela usuarios, priorizando senha_hash."""
    cols = get_table_columns(conn, "usuarios")
    if "senha_hash" in cols:
        return "senha_hash"
    if "senha" in cols:
        return "senha"
    return "senha_hash"


def _extract_password_hash(user_row: dict | None) -> str:
    if not user_row:
        return ""
    return str(user_row.get("senha_hash") or user_row.get("senha") or "")


def _get_session_store() -> dict:
    """Return Streamlit session_state when available, else module-local fallback store."""
    try:
        st_mod = importlib.import_module("streamlit")
        return st_mod.session_state
    except Exception:
        return _FALLBACK_COOKIE_STORE


def _get_cookie_manager():
    global _COOKIE_MANAGER_INSTANCE
    if _COOKIE_MANAGER_INSTANCE is not None:
        return _COOKIE_MANAGER_INSTANCE

    if os.environ.get("COOKIE_BACKEND_SUPPORTS_HTTPONLY", "").strip().lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "COOKIE_BACKEND_SUPPORTS_HTTPONLY=true deve confirmar explicitamente um backend capaz de emitir HttpOnly."
        )

    if stx is None:
        raise RuntimeError(
            "Contrato de sessao indisponivel: extra-streamlit-components e obrigatorio para o cookie seguro."
        )
    _COOKIE_MANAGER_INSTANCE = stx.CookieManager(key=_COOKIE_MANAGER_KEY)
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
    email = normalize_email_identifier(email)
    with db_connect() as conn:
        pwd_col = _get_usuarios_password_column(conn)
        c = conn.cursor()
        c.execute(
            f"SELECT id, nome, email, {pwd_col} AS senha_hash, perfil, status FROM usuarios WHERE email=%s",
            (email,),
        )
        user = c.fetchone()
    if user and check_password(senha, _extract_password_hash(user)):
        return user
    return None

# --- GERAÇÃO E DECODIFICAÇÃO DE TOKEN JWT ---
def generate_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Gera um JWT para o usuário autenticado, incluindo o nome."""
    jwt_secret = _get_jwt_secret()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=JWT_EXP_MINUTES)
    jti = uuid.uuid4().hex
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(session_version, 0) AS session_version FROM usuarios WHERE id=%s", (int(user_id),))
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Usuario inexistente ao emitir sessao.")
        session_version = int(row["session_version"] or 0)
        # Rotacao: uma nova autenticacao encerra JTIs ativos anteriores.
        cursor.execute(
            "UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=%s AND revoked_at IS NULL",
            (int(user_id),),
        )
        cursor.execute(
            "INSERT INTO auth_sessions (jti,user_id,session_version,issued_at,expires_at) VALUES (%s,%s,%s,%s,%s)",
            (jti, int(user_id), session_version, issued_at, expires_at),
        )
        conn.commit()
    payload = {
        "user_id": user_id,
        "nome": nome,
        "perfil": perfil,
        "status": status,
        "jti": jti,
        "sv": session_version,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_token(token: str):
    """Decodifica e valida um JWT; retorna o payload, ou None se inválido/expirado."""
    try:
        jwt_secret = _get_jwt_secret()
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"], options={"require": ["exp", "iat", "jti", "user_id", "sv"]})
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT 1 FROM auth_sessions s JOIN usuarios u ON u.id=s.user_id
                   WHERE s.jti=%s AND s.user_id=%s AND s.revoked_at IS NULL
                     AND s.expires_at>CURRENT_TIMESTAMP
                     AND s.session_version=u.session_version AND s.session_version=%s LIMIT 1""",
                (str(payload["jti"]), int(payload["user_id"]), int(payload["sv"])),
            )
            if cursor.fetchone() is None:
                return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except Exception:
        return None

# --- REGISTRO DE USUÁRIO ---
def cadastrar_usuario(nome: str, email: str, senha: str, perfil="participante", status="Ativo") -> bool:
    """Cria novo usuário, garantindo unicidade de email."""
    from services.access_control import require_operation
    require_operation("usuario.write")
    try:
        senha_hashed = hash_password(senha)
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'usuarios')
            pwd_col = _get_usuarios_password_column(conn)
            if 'faltas' in cols:
                # Inserção compatível com PostgreSQL, retornando o id criado.
                c.execute(
                    f'INSERT INTO usuarios (nome, email, {pwd_col}, perfil, status, faltas) '
                    'VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                    (nome, email, senha_hashed, perfil, status, 0)
                )
            else:
                c.execute(
                    f'INSERT INTO usuarios (nome, email, {pwd_col}, perfil, status) '
                    'VALUES (%s, %s, %s, %s, %s) RETURNING id',
                    (nome, email, senha_hashed, perfil, status)
                )
            row = c.fetchone()
            user_id = row['id'] if row else None
            conn.commit()
        clear_data_cache()
        try:
            if isinstance(user_id, int):
                from db.repo_users import registrar_historico_status_usuario
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
        # fix #3: logar exceção para diagnóstico em vez de engolir silenciosamente
        logger.exception("cadastrar_usuario falhou para email=%s", email)
        return False

# --- BUSCA DE USUÁRIOS ---
def get_user_by_email(email: str):
    with db_connect() as conn:
        pwd_col = _get_usuarios_password_column(conn)
        c = conn.cursor()
        c.execute(
            f"SELECT id, nome, email, {pwd_col} AS senha_hash, perfil, status FROM usuarios WHERE email=%s",
            (email,)
        )
        user = c.fetchone()
    return user

# fix #4: get_user_by_id removido daqui — importado de db.repo_users.

# --- GESTÃO DE COOKIES (para login) ---
def set_auth_cookies(token, expires_minutes=JWT_EXP_MINUTES):
    """Salva o token JWT em cookie para restaurar a sessão."""
    cookie_manager = _get_cookie_manager()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    cookie_manager.set(
        "session_token", token, expires_at=expires_at,
        options={"path": "/", "secure": True, "httponly": True, "samesite": "Strict"},
    )


def revoke_token(token: str | None) -> None:
    if not token:
        return
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"], options={"verify_exp": False})
        jti = payload.get("jti")
        if jti:
            with db_connect() as conn:
                conn.cursor().execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE jti=%s AND revoked_at IS NULL", (str(jti),))
                conn.commit()
    except Exception as exc:
        logger.warning("Falha ao revogar token de sessao: %s", exc)

def clear_auth_cookies(token: str | None = None):
    if token is None:
        token = _get_session_store().get("token")
    revoke_token(token)
    cookie_manager = _get_cookie_manager()
    cookie_manager.set(
        "session_token", "", expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        options={"path": "/", "secure": True, "httponly": True, "samesite": "Strict"},
    )


def get_auth_cookie_token():
    """Retorna token de sessão salvo em cookie, quando disponível."""
    cookie_manager = _get_cookie_manager()
    try:
        cookies = cookie_manager.get_all()
        if isinstance(cookies, dict):
            token = cookies.get("session_token")
            if token:
                return str(token)
    except Exception as exc:
        raise RuntimeError("Falha ao ler o cookie de sessao seguro.") from exc
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
    email = normalize_email_identifier(email)
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
            "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE email=%s AND used_at IS NULL",
            (email,),
        )
        c.execute(
            "INSERT INTO password_reset_tokens (email, token_hash, expires_at) VALUES (%s, %s, %s)",
            (email, token_hash, expires_at),
        )
        conn.commit()

    return True, (usuario['nome'], reset_token, RESET_TOKEN_EXP_MINUTES)


def redefinir_senha_com_token(email: str, token: str, nova_senha: str):
    email = normalize_email_identifier(email)
    token_hash = _hash_reset_token(token)
    now_utc = datetime.now(timezone.utc)

    with db_connect() as conn:
        _ensure_password_reset_table(conn)
        c = conn.cursor()
        c.execute(
            """
            SELECT id, token_hash
            FROM password_reset_tokens
            WHERE email = %s
              AND used_at IS NULL
              AND expires_at > %s
            ORDER BY id DESC
            LIMIT 10
            FOR UPDATE
            """,
            (email, now_utc),
        )
        token_row = None
        for candidate in (c.fetchall() or []):
            matches = hmac.compare_digest(str(candidate["token_hash"]), token_hash)
            if matches:
                token_row = candidate
        if not token_row:
            return False, "Token inválido ou expirado."

        c.execute(
            "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=%s AND used_at IS NULL RETURNING id",
            (token_row["id"],),
        )
        if c.fetchone() is None:
            return False, "Token inválido ou expirado."

        senha_hashed = hash_password(nova_senha)
        pwd_col = _get_usuarios_password_column(conn)
        cols = get_table_columns(conn, 'usuarios')
        if 'must_change_password' in cols:
            c.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'usuarios'
                  AND column_name = 'must_change_password'
                """
            )
            type_row = c.fetchone() or {}
            data_type = str(type_row.get('data_type', '')).strip().lower()
            must_change_value = False if data_type == 'boolean' else 0
            c.execute(
                f"UPDATE usuarios SET {pwd_col}=%s, must_change_password=%s, session_version=COALESCE(session_version,0)+1 WHERE email=%s",
                (senha_hashed, must_change_value, email),
            )
        else:
            c.execute(f"UPDATE usuarios SET {pwd_col}=%s, session_version=COALESCE(session_version,0)+1 WHERE email=%s", (senha_hashed, email))

        c.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=(SELECT id FROM usuarios WHERE email=%s) AND revoked_at IS NULL", (email,))

        conn.commit()
    clear_data_cache()

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
        pwd_col = _get_usuarios_password_column(conn)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS cnt FROM usuarios WHERE perfil = %s", ('master',))
        existe = c.fetchone()['cnt'] > 0
        if not existe:
            senha_hashed = hash_password(senha)
            cols = get_table_columns(conn, 'usuarios')
            if 'faltas' in cols:
                c.execute(
                    f"INSERT INTO usuarios (nome, email, {pwd_col}, perfil, status, faltas) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (nome, email, senha_hashed, 'master', 'Ativo', 0)
                )
            else:
                c.execute(
                    f"INSERT INTO usuarios (nome, email, {pwd_col}, perfil, status) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (nome, email, senha_hashed, 'master', 'Ativo')
                )
            conn.commit()
            clear_data_cache()

# Alias para compatibilidade
def create_token(user_id: int, nome: str, perfil: str, status: str) -> str:
    """Alias para generate_token - cria um JWT para o usuário autenticado."""
    return generate_token(user_id, nome, perfil, status)
