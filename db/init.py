"""
Módulo de Banco de Dados - BF1Dev 3.0
Inicializa pool de conexões, migrations e master user
"""

import logging
import sys
from pathlib import Path

# ============ CONFIGURAÇÃO DE LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bf1dev.log', encoding='utf-8')
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
    DB_PATH,
    POOL_SIZE,
    DB_TIMEOUT,
    CACHE_TTL_CURTO,
    CACHE_TTL_MEDIO,
    CACHE_TTL_LONGO,
    BCRYPT_ROUNDS,
    SESSION_TIMEOUT,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION,
    INDICES
)

# Database Utilities
from db.db_utils import (
    init_db,
    db_connect,
    hash_password,
    check_password,
    get_user_by_email,
    get_user_by_id,
    get_master_user,
    cadastrar_usuario,
    autenticar_usuario,
    get_usuarios_df,
    get_pilotos_df,
    get_provas_df,
    get_apostas_df,
    get_resultados_df,
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
    """
    Inicializa o banco de dados completo
    Executa ordem correta: pool → db → migrations → master user
    """
    try:
        logger.info("🚀 Inicializando BF1Dev 3.0 Database Layer...")
        
        # 1. Inicializar pool de conexões
        logger.info("1️⃣  Inicializando pool de conexões...")
        init_pool(str(DB_PATH), POOL_SIZE)
        logger.info(f"   ✓ Pool criado: {POOL_SIZE} conexões")
        
        # 2. Criar tabelas base
        logger.info("2️⃣  Criando tabelas do banco de dados...")
        init_db()
        logger.info("   ✓ Tabelas criadas/verificadas")
        
        # 3. Executar migrations (índices)
        logger.info("3️⃣  Executando migrations (criando índices)...")
        try:
            run_migrations()
            logger.info("   ✓ Migrations executadas com sucesso")
        except Exception as e:
            logger.warning(f"   ⚠️  Migrations já foram executadas: {str(e)[:50]}")
        
        # 4. Criar usuário Master automaticamente
        logger.info("4️⃣  Verificando usuário Master...")
        if MasterUserManager.create_master_user():
            logger.info("   ✓ Usuário Master criado")
        else:
            logger.info("   ✓ Usuário Master já existe")
        
        logger.info("✅ Banco de dados inicializado com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        logger.error("Abortando inicialização...")
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
    # Pool
    'init_pool',
    'get_pool',
    'close_pool',
    'ConnectionPool',
    
    # Config
    'DB_PATH',
    'POOL_SIZE',
    'DB_TIMEOUT',
    'CACHE_TTL_CURTO',
    'CACHE_TTL_MEDIO',
    'CACHE_TTL_LONGO',
    'BCRYPT_ROUNDS',
    'SESSION_TIMEOUT',
    'MAX_LOGIN_ATTEMPTS',
    'LOCKOUT_DURATION',
    'INDICES',
    
    # DB Utils
    'init_db',
    'db_connect',
    'hash_password',
    'check_password',
    'get_user_by_email',
    'get_user_by_id',
    'get_master_user',
    'cadastrar_usuario',
    'autenticar_usuario',
    'get_usuarios_df',
    'get_pilotos_df',
    'get_provas_df',
    'get_apostas_df',
    'get_resultados_df',
    'registrar_log_aposta',
    'log_aposta_existe',
    
    # Migrations
    'run_migrations',
    
    # Master Manager
    'MasterUserManager',
    
    # Backup
    'backup_banco',
    'restaurar_backup',
    
    # Init
    'initialize_database',
]

logger.info("✓ Módulo 'db' carregado com sucesso")
