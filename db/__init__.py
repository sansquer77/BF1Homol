"""
Módulo de Banco de Dados - BF1 3.0
Inicializa pool de conexões, migrations e master user
"""

import logging
import sys

# ============ CONFIGURAÇÃO DE LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bf1.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ============ IMPORTAÇÕES ============

# Connection Pool
from db.connection_pool import (
    init_pool,
    get_pool,
    close_pool,
    ConnectionPool
)

# Configurações
from db.db_config import (
    POOL_SIZE,
    DB_TIMEOUT,
    CACHE_TTL_CURTO,
    CACHE_TTL_MEDIO,
    CACHE_TTL_LONGO,
    BCRYPT_ROUNDS,
    SESSION_TIMEOUT,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION,
    MAX_RESET_ATTEMPTS,
    RESET_LOCKOUT_DURATION,
    INDICES
)

# Database Access
from db.db_schema import (
    init_db,
    db_connect,
)
from db.repo_users import (
    hash_password,
    check_password,
    get_user_by_email,
    get_user_by_id,
    get_master_user,
    cadastrar_usuario,
    autenticar_usuario,
    get_usuarios_df,
)
from db.repo_races import (
    get_pilotos_df,
    get_provas_df,
    get_resultados_df,
)
from db.repo_bets import (
    get_apostas_df,
)
from db.repo_logs import (
    registrar_log_aposta,
    log_aposta_existe
)

# Migrations
from db.migrations import run_migrations

# Master User Manager
from db.master_user_manager import MasterUserManager

# Backup Utils
from db.backup_utils import backup_banco, restaurar_backup

# ============ INICIALIZAÇÃO AUTOMÁTICA ============

def initialize_database():
    """Inicializa o banco de dados completo"""
    try:
        logger.info("🚀 Inicializando BF1 3.0 Database Layer...")
        
        logger.info("1️⃣  Inicializando pool de conexões...")
        init_pool(pool_size=POOL_SIZE)
        logger.info(f"   ✓ Pool criado: {POOL_SIZE} conexões")
        
        logger.info("2️⃣  Executando migrations (schema + índices)...")
        try:
            run_migrations()
            logger.info("   ✓ Migrations executadas com sucesso")
        except Exception as e:
            logger.warning(f"   ⚠️  Migrations já foram executadas: {str(e)[:50]}")

        logger.info("3️⃣  Verificando usuário Master...")
        if MasterUserManager.create_master_user():
            logger.info("   ✓ Usuário Master criado")
        else:
            logger.info("   ✓ Usuário Master já existe")
        
        logger.info("✅ Banco de dados inicializado com sucesso!\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        raise


# ============ ATEXIT HANDLER ============

import atexit

def cleanup_on_exit():
    """Limpa recursos ao encerrar aplicação"""
    try:
        logger.info("🔌 Fechando pool de conexões...")
        close_pool()
        logger.info("✓ Pool fechado com sucesso")
    except Exception as e:
        logger.warning(f"Aviso ao fechar pool: {e}")

atexit.register(cleanup_on_exit)

# ============ EXPORT PUBLIC API ============

__all__ = [
    'init_pool', 'get_pool', 'close_pool', 'ConnectionPool',
    'POOL_SIZE', 'DB_TIMEOUT', 'CACHE_TTL_CURTO', 'CACHE_TTL_MEDIO', 'CACHE_TTL_LONGO',
    'BCRYPT_ROUNDS', 'SESSION_TIMEOUT', 'MAX_LOGIN_ATTEMPTS', 'LOCKOUT_DURATION', 'MAX_RESET_ATTEMPTS', 'RESET_LOCKOUT_DURATION', 'INDICES',
    'init_db', 'db_connect', 'hash_password', 'check_password', 'get_user_by_email', 'get_user_by_id',
    'get_master_user', 'cadastrar_usuario', 'autenticar_usuario', 'get_usuarios_df', 'get_pilotos_df',
    'get_provas_df', 'get_apostas_df', 'get_resultados_df', 'registrar_log_aposta', 'log_aposta_existe',
    'run_migrations', 'MasterUserManager', 'backup_banco', 'restaurar_backup', 'initialize_database',
]

logger.info("✓ Módulo 'db' carregado com sucesso")
