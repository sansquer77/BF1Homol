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
    - `equipe`, `status` e `numero` em `pilotos`
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
            if 'numero' not in cols:
                cursor.execute("ALTER TABLE pilotos ADD COLUMN numero INTEGER DEFAULT 0")
                logger.info("✓ Coluna `numero` adicionada a `pilotos`")

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
    current_year = datetime.datetime.now().year
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Tabela championship_bets (agora com coluna season e UNIQUE por usuário+season)
            cursor.execute("PRAGMA table_info('championship_bets')")
            bets_cols = cursor.fetchall()
            has_bets = bool(bets_cols)
            bets_has_season = any(col[1] == 'season' for col in bets_cols)
            cursor.execute("PRAGMA index_list('championship_bets')")
            idx_list = cursor.fetchall()
            has_user_season_unique = False
            has_old_user_unique = False
            for idx in idx_list:
                idx_name = idx[1]
                is_unique = bool(idx[2])
                if not is_unique:
                    continue
                cursor.execute(f"PRAGMA index_info('{idx_name}')")
                cols_for_idx = [r[2] for r in cursor.fetchall()]
                if cols_for_idx == ['user_id']:
                    has_old_user_unique = True
                if cols_for_idx == ['user_id', 'season']:
                    has_user_season_unique = True

            if not has_bets:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS championship_bets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        user_nome TEXT NOT NULL,
                        champion TEXT NOT NULL,
                        vice TEXT NOT NULL,
                        team TEXT NOT NULL,
                        season INTEGER NOT NULL,
                        bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES usuarios(id),
                        UNIQUE(user_id, season)
                    )
                ''')
                logger.info("✓ Tabela `championship_bets` criada com coluna season")
            else:
                # Se não tiver season ou a UNIQUE antiga (apenas user_id), recria com o novo esquema
                needs_rebuild = (not bets_has_season) or (not has_user_season_unique) or has_old_user_unique
                if needs_rebuild:
                    logger.info("↻ Atualizando `championship_bets` para suportar temporadas...")
                    cursor.execute("PRAGMA foreign_keys=OFF")
                    cursor.execute("BEGIN")
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS championship_bets__new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            user_nome TEXT NOT NULL,
                            champion TEXT NOT NULL,
                            vice TEXT NOT NULL,
                            team TEXT NOT NULL,
                            season INTEGER NOT NULL,
                            bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES usuarios(id),
                            UNIQUE(user_id, season)
                        )
                    ''')
                    # Copia dados antigos colocando season padrão no ano atual
                    cursor.execute('''
                        INSERT INTO championship_bets__new (user_id, user_nome, champion, vice, team, season, bet_time)
                        SELECT user_id, user_nome, champion, vice, team, ?, bet_time
                        FROM championship_bets
                    ''', (current_year,))
                    cursor.execute("DROP TABLE championship_bets")
                    cursor.execute("ALTER TABLE championship_bets__new RENAME TO championship_bets")
                    cursor.execute("COMMIT")
                    cursor.execute("PRAGMA foreign_keys=ON")
                    logger.info("✓ `championship_bets` agora tem coluna season e UNIQUE(user_id, season)")
                else:
                    logger.debug("  `championship_bets` já compatível com temporadas")

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
            cursor.execute("PRAGMA table_info('championship_bets_log')")
            log_cols = cursor.fetchall()
            log_has_season = any(col[1] == 'season' for col in log_cols)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS championship_bets_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_nome TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    season INTEGER NOT NULL DEFAULT {current_year},
                    bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                )
            ''')
            logger.info("✓ Tabela `championship_bets_log` criada ou já existe")
            if log_cols and not log_has_season:
                try:
                    cursor.execute(f"ALTER TABLE championship_bets_log ADD COLUMN season INTEGER NOT NULL DEFAULT {current_year}")
                    cursor.execute(f"UPDATE championship_bets_log SET season = {current_year} WHERE season IS NULL")
                    logger.info("✓ Coluna season adicionada a `championship_bets_log`")
                except Exception as e:
                    logger.debug(f"  Falha ao adicionar season em championship_bets_log: {e}")

            # Tabela log_apostas (garante colunas compatíveis com UI de log)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS log_apostas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER,
                    prova_id INTEGER,
                    apostador TEXT,
                    aposta TEXT,
                    nome_prova TEXT,
                    pilotos TEXT,
                    piloto_11 TEXT,
                    tipo_aposta INTEGER,
                    automatica INTEGER,
                    data TEXT,
                    horario TIMESTAMP,
                    temporada TEXT DEFAULT '{current_year}',
                    status TEXT DEFAULT 'Registrada',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (prova_id) REFERENCES provas(id)
                )
            ''')
            logger.info("✓ Tabela `log_apostas` criada ou já existe")

            # Rebuild log_apostas if legacy columns missing
            cursor.execute("PRAGMA table_info('log_apostas')")
            log_cols = [r[1] for r in cursor.fetchall()]
            required_cols = {"apostador", "aposta", "nome_prova", "tipo_aposta", "automatica", "data", "horario", "temporada"}
            has_required = required_cols.issubset(set(log_cols))
            if not has_required:
                logger.info("↻ Atualizando `log_apostas` para incluir colunas de temporada e metadados de aposta...")
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("BEGIN")
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS log_apostas__new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        usuario_id INTEGER,
                        prova_id INTEGER,
                        apostador TEXT,
                        aposta TEXT,
                        nome_prova TEXT,
                        pilotos TEXT,
                        piloto_11 TEXT,
                        tipo_aposta INTEGER,
                        automatica INTEGER,
                        data TEXT,
                        horario TIMESTAMP,
                        temporada TEXT DEFAULT '{current_year}',
                        status TEXT DEFAULT 'Registrada',
                        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                        FOREIGN KEY (prova_id) REFERENCES provas(id)
                    )
                ''')
                # Copia dados legados, mapeando o que existir
                cursor.execute("PRAGMA table_info('log_apostas')")
                legacy_cols = [r[1] for r in cursor.fetchall()]
                has_col = lambda name: name in legacy_cols
                insert_sql = '''
                    INSERT INTO log_apostas__new (usuario_id, prova_id, apostador, aposta, nome_prova, pilotos, piloto_11, tipo_aposta, automatica, data, horario, temporada, status, data_criacao)
                    SELECT 
                        usuario_id,
                        prova_id,
                        NULL,
                        CASE WHEN {has_pilotos} THEN pilotos ELSE NULL END,
                        NULL,
                        CASE WHEN {has_pilotos} THEN pilotos ELSE NULL END,
                        CASE WHEN {has_piloto11} THEN piloto_11 ELSE NULL END,
                        0,
                        0,
                        DATE(CASE WHEN {has_data_criacao} THEN data_criacao ELSE CURRENT_TIMESTAMP END),
                        CASE WHEN {has_data_criacao} THEN data_criacao ELSE CURRENT_TIMESTAMP END,
                        '{current_year}',
                        CASE WHEN {has_status} THEN status ELSE 'Registrada' END,
                        CASE WHEN {has_data_criacao} THEN data_criacao ELSE CURRENT_TIMESTAMP END
                    FROM log_apostas
                '''.format(
                    has_pilotos='1' if has_col('pilotos') else '0',
                    has_piloto11='1' if has_col('piloto_11') else '0',
                    has_data_criacao='1' if has_col('data_criacao') else '0',
                    has_status='1' if has_col('status') else '0'
                )
                cursor.execute(insert_sql)
                cursor.execute("DROP TABLE log_apostas")
                cursor.execute("ALTER TABLE log_apostas__new RENAME TO log_apostas")
                cursor.execute("COMMIT")
                cursor.execute("PRAGMA foreign_keys=ON")
                logger.info("✓ `log_apostas` atualizada para estrutura completa")

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
