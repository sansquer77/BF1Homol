"""
Configurações Centralizadas do Banco de Dados
Facilita manutenção e padronização
Suporta variáveis de ambiente para produção
"""

from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

def _can_write_database_path(db_path: Path) -> bool:
    """Valida se o diretório do banco é gravável no runtime atual."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    probe_file = db_path.parent / f".db_write_probe_{os.getpid()}"
    try:
        probe_file.touch(exist_ok=True)
        probe_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolve_db_path() -> Path:
    """
    Resolve caminho do banco com fallback seguro para /tmp em ambientes read-only.

    Prioridade:
      1) DATABASE_PATH (se gravável)
      2) arquivo na raiz do projeto (se gravável)
      3) /tmp/bolao_f1.db
    """
    env_db_path = os.environ.get("DATABASE_PATH")
    if env_db_path:
        candidate = Path(env_db_path).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()

        if _can_write_database_path(candidate):
            return candidate

        logger.warning(
            "DATABASE_PATH=%s não é gravável. Usando fallback em /tmp.",
            candidate,
        )

    default_db = Path(__file__).parent.parent / "bolao_f1.db"
    if _can_write_database_path(default_db):
        return default_db

    fallback_db = Path("/tmp") / "bolao_f1.db"
    fallback_db.parent.mkdir(parents=True, exist_ok=True)
    logger.warning(
        "Diretório do projeto não é gravável. Banco SQLite será usado em %s.",
        fallback_db,
    )
    return fallback_db


# Caminho do banco de dados - suporta variável de ambiente
DB_PATH = _resolve_db_path()

# Configurações de Pool
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
DB_TIMEOUT = float(os.environ.get("DB_TIMEOUT", "30.0"))

# Configurações de Cache
CACHE_TTL_CURTO = int(os.environ.get("CACHE_TTL_CURTO", "300"))  # 5 minutos
CACHE_TTL_MEDIO = int(os.environ.get("CACHE_TTL_MEDIO", "3600"))  # 1 hora
CACHE_TTL_LONGO = int(os.environ.get("CACHE_TTL_LONGO", "86400"))  # 24 horas

# Índices para otimização (criados em migrations.py)
INDICES = {
    "usuarios": [
        "CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_perfil ON usuarios(perfil)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_status ON usuarios(status)",
    ],
    "apostas": [
        "CREATE INDEX IF NOT EXISTS idx_apostas_usuario ON apostas(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_prova ON apostas(prova_id)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_data ON apostas(data_envio)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_temporada ON apostas(temporada)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_usuario_prova_temporada ON apostas(usuario_id, prova_id, temporada)",
    ],
    "provas": [
        "CREATE INDEX IF NOT EXISTS idx_provas_data ON provas(data)",
        "CREATE INDEX IF NOT EXISTS idx_provas_status ON provas(status)",
        "CREATE INDEX IF NOT EXISTS idx_provas_temporada_data ON provas(temporada, data)",
    ],
    "resultados": [
        "CREATE INDEX IF NOT EXISTS idx_resultados_prova ON resultados(prova_id)",
        "CREATE INDEX IF NOT EXISTS idx_resultados_prova_temporada ON resultados(prova_id, temporada)",
    ],
}

# Configurações de Segurança
BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "12"))
SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "3600"))  # 1 hora em segundos
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))  # 15 minutos
MAX_RESET_ATTEMPTS = int(os.environ.get("MAX_RESET_ATTEMPTS", "3"))
RESET_LOCKOUT_DURATION = int(os.environ.get("RESET_LOCKOUT_DURATION", "900"))  # 15 minutos
