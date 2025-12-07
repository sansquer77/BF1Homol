"""
Sistema de Migrations para Criar e Otimizar Tabelas
Adiciona índices para melhor performance
"""

from pathlib import Path
import datetime
from db.connection_pool import get_pool
from db.db_config import INDICES
from db.db_utils import init_db
import logging

logger = logging.getLogger(__name__)


def add_temporada_columns_if_missing():
    """
    Adiciona coluna `temporada` a tabelas de provas, apostas e resultados.
    Idempotent: não faz nada se a coluna já existe.
    """
    pool = get_pool()
    tables_to_update = {
        'provas': 'Adiciona temporada às provas',
        'apostas': 'Adiciona temporada às apostas',
        'resultados': 'Adiciona temporada aos resultados',
        'posicoes_participantes': 'Adiciona temporada às posições'
    }
    
    current_year = str(datetime.datetime.now().year)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for table_name, description in tables_to_update.items():
            try:
                # Check if table exists and if temporada column is missing
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                cols = [r[1] for r in cursor.fetchall()]
                
                if 'temporada' not in cols:
                    # Add temporada column with default value
                    cursor.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN temporada TEXT DEFAULT '{current_year}'"
                    )
                    logger.info(f"✓ Coluna `temporada` adicionada a `{table_name}`")
                else:
                    logger.debug(f"  Coluna `temporada` já existe em `{table_name}`, pulando...")
            except Exception as e:
                logger.debug(f"  Skipping {table_name}: {e}")
        
        conn.commit()


def add_legacy_columns_if_missing():
    """
    Adiciona colunas presentes no schema legado mas que podem faltar em bancos antigos:
    - `equipe` e `status` em `pilotos`
    - `horario_prova` e `tipo` em `provas`
    Idempotent: não faz nada se a coluna já existe.
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Pilotos
            cursor.execute("PRAGMA table_info('pilotos')")
            cols = [r[1] for r in cursor.fetchall()]
            if 'equipe' not in cols:
                cursor.execute("ALTER TABLE pilotos ADD COLUMN equipe TEXT DEFAULT ''")
                logger.info("✓ Coluna `equipe` adicionada a `pilotos`")
            if 'status' not in cols:
                cursor.execute("ALTER TABLE pilotos ADD COLUMN status TEXT DEFAULT 'Ativo'")
                logger.info("✓ Coluna `status` adicionada a `pilotos`")

            # Provas
            cursor.execute("PRAGMA table_info('provas')")
            cols = [r[1] for r in cursor.fetchall()]
            if 'horario_prova' not in cols:
                cursor.execute("ALTER TABLE provas ADD COLUMN horario_prova TEXT DEFAULT ''")
                logger.info("✓ Coluna `horario_prova` adicionada a `provas`")
            if 'tipo' not in cols:
                cursor.execute("ALTER TABLE provas ADD COLUMN tipo TEXT DEFAULT 'Normal'")
                logger.info("✓ Coluna `tipo` adicionada a `provas`")

            conn.commit()
        except Exception as e:
            logger.debug(f"Erro ao adicionar colunas legadas: {e}")
            conn.rollback()

def create_missing_tables_if_needed():
    """
    Cria tabelas faltando se necessário (championship_bets, championship_results, log_apostas).
    Idempotent: usa CREATE TABLE IF NOT EXISTS.
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Tabela championship_bets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS championship_bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_nome TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id),
                    UNIQUE(user_id)
                )
            ''')
            logger.info("✓ Tabela `championship_bets` criada ou já existe")

            # Tabela championship_results
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS championship_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season INTEGER NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    UNIQUE(season)
                )
            ''')
            logger.info("✓ Tabela `championship_results` criada ou já existe")

            # Tabela championship_bets_log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS championship_bets_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_nome TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                )
            ''')
            logger.info("✓ Tabela `championship_bets_log` criada ou já existe")

            # Tabela log_apostas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_apostas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL,
                    prova_id INTEGER NOT NULL,
                    pilotos TEXT,
                    piloto_11 TEXT,
                    status TEXT DEFAULT 'Registrada',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (prova_id) REFERENCES provas(id)
                )
            ''')
            logger.info("✓ Tabela `log_apostas` criada ou já existe")

            conn.commit()
        except Exception as e:
            logger.debug(f"Erro ao criar tabelas faltando: {e}")
            conn.rollback()


def run_migrations():
    """
    Executa todas as migrations de banco de dados
    Cria índices para otimização de queries
    """
    # Primeiro, criar tabelas base se não existirem
    init_db()
    
    pool = get_pool()
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        try:
            # Criar tabelas faltando
            create_missing_tables_if_needed()
            # Adicionar colunas temporada (plurianual support)
            add_temporada_columns_if_missing()
            # Adicionar colunas legadas que podem faltar em bancos antigos
            add_legacy_columns_if_missing()
            
            # Criar índices para usuários
            for idx in INDICES.get("usuarios", []):
                cursor.execute(idx)
                logger.info(f"✓ Índice criado: {idx.split('IF NOT EXISTS')[1].strip()}")
            
            # Criar índices para apostas
            for idx in INDICES.get("apostas", []):
                cursor.execute(idx)
                logger.info(f"✓ Índice criado: {idx.split('IF NOT EXISTS')[1].strip()}")
            
            # Criar índices para provas
            for idx in INDICES.get("provas", []):
                cursor.execute(idx)
                logger.info(f"✓ Índice criado: {idx.split('IF NOT EXISTS')[1].strip()}")
            
            # Criar índices para resultados
            for idx in INDICES.get("resultados", []):
                cursor.execute(idx)
                logger.info(f"✓ Índice criado: {idx.split('IF NOT EXISTS')[1].strip()}")
            
            conn.commit()
            logger.info("✓ Todas as migrations executadas com sucesso!")
            
        except Exception as e:
            logger.error(f"✗ Erro ao executar migrations: {e}")
            conn.rollback()
            raise

def create_hall_da_fama_table():
    """
    Cria a tabela hall_da_fama para armazenar resultados anuais independentes
    """
    try:
        with get_pool().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hall_da_fama (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL,
                    temporada TEXT NOT NULL,
                    posicao_final INTEGER NOT NULL,
                    pontos REAL DEFAULT 0,
                    UNIQUE(usuario_id, temporada),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
            ''')
            conn.commit()
            logger.info("✓ Tabela hall_da_fama criada com sucesso")
    except Exception as e:
        logger.error(f"Erro ao criar tabela hall_da_fama: {e}")
        raise

# Executar quando o módulo é importado
try:
    create_hall_da_fama_table()
except:
    pass
