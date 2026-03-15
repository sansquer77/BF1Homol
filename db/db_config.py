"""
Configurações Centralizadas do Banco de Dados
Facilita manutenção e padronização
Suporta variáveis de ambiente para produção
"""

from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH_SOURCE = ""


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

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
    Resolve caminho do banco com prioridade para volume persistente em /data.

    Prioridade:
      1) variável de ambiente DB_PATH
      2) variável de ambiente DATABASE_PATH
      3) /data/bolao_f1.db
      4) bolao_f1.db na raiz do projeto (fallback para desenvolvimento)
      5) /tmp/bolao_f1.db (fallback final)
    """
    global DB_PATH_SOURCE

    strict_env_path = _env_flag("DB_PATH_STRICT", default=False)
    env_db_path = os.environ.get("DB_PATH") or os.environ.get("DATABASE_PATH")
    if env_db_path:
        candidate = Path(env_db_path).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()

        if _can_write_database_path(candidate):
            DB_PATH_SOURCE = "environment"
            return candidate

        message = (
            "DB_PATH/DATABASE_PATH foi definido no ambiente, mas não é gravável: "
            f"{candidate}. Corrija a montagem/permissão do volume."
        )
        if strict_env_path:
            raise RuntimeError(message)
        logger.error("%s Continuando com fallback por DB_PATH_STRICT=false.", message)

    data_db = Path("/data") / "bolao_f1.db"
    if _can_write_database_path(data_db):
        DB_PATH_SOURCE = "default:/data"
        return data_db

    project_db = Path(__file__).parent.parent / "bolao_f1.db"
    if _can_write_database_path(project_db):
        logger.warning(
            "/data não disponível para escrita. Usando banco local em %s.",
            project_db,
        )
        DB_PATH_SOURCE = "fallback:project-root"
        return project_db

    fallback_db = Path("/tmp") / "bolao_f1.db"
    fallback_db.parent.mkdir(parents=True, exist_ok=True)
    logger.warning(
        "Nem /data nem diretório do projeto são graváveis. Banco SQLite será usado em %s.",
        fallback_db,
    )
    DB_PATH_SOURCE = "fallback:/tmp"
    return fallback_db


def _resolve_backup_dir(db_path: Path) -> Path:
    """Resolve diretório de backups no mesmo volume do banco (ou via BACKUP_DIR)."""
    env_backup_dir = os.environ.get("BACKUP_DIR")
    if env_backup_dir:
        candidate = Path(env_backup_dir).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            logger.warning(
                "BACKUP_DIR=%s não está acessível. Usando fallback no volume do banco.",
                candidate,
            )

    default_backup_dir = db_path.parent / "backups"
    try:
        default_backup_dir.mkdir(parents=True, exist_ok=True)
        return default_backup_dir
    except OSError:
        fallback_backup_dir = Path("/tmp") / "backups"
        fallback_backup_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "Não foi possível criar diretório de backup no volume principal. Usando %s.",
            fallback_backup_dir,
        )
        return fallback_backup_dir


# Caminho do banco de dados - suporta variável de ambiente
DB_PATH = _resolve_db_path()
logger.info("DB_PATH resolvido para %s (source=%s)", DB_PATH, DB_PATH_SOURCE)

# Diretório para backups automáticos/restauração
BACKUP_DIR = _resolve_backup_dir(DB_PATH)

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
