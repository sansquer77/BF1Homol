"""
Utilitários de Banco de Dados - Versão 3.0
Melhorias: bcrypt para senhas, pool de conexões, caching
"""

import sqlite3
import pandas as pd
from pathlib import Path
import bcrypt
import logging
from typing import Optional, Dict
from db.connection_pool import get_pool, init_pool
from db.db_config import BCRYPT_ROUNDS, DB_PATH

logger = logging.getLogger(__name__)

import datetime

# Inicializar pool ao importar
init_pool(str(DB_PATH))

# ============ FUNÇÕES DE CONEXÃO ============

def db_connect():
    """Retorna uma conexão do pool"""
    return get_pool().get_connection()

# ============ FUNÇÕES DE SEGURANÇA (BCRYPT) ============

def hash_password(senha: str) -> str:
    """
    Hash seguro de senha usando bcrypt
    
    Args:
        senha: Senha em texto plano
    
    Returns:
        Hash da senha (bcrypt)
    """
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def check_password(senha: str, hash_senha: str) -> bool:
    """
    Verifica se a senha corresponde ao hash
    
    Args:
        senha: Senha em texto plano
        hash_senha: Hash do bcrypt
    
    Returns:
        True se a senha é válida
    """
    try:
        return bcrypt.checkpw(senha.encode('utf-8'), hash_senha.encode('utf-8'))
    except (ValueError, TypeError):
        logger.error("Erro ao verificar password - hash inválido")
        return False

# ============ TABELAS ============

def init_db():
    """Inicializa o banco de dados com todas as tabelas necessárias"""
    # Cria o esquema compatível com o dump histórico (pilotos com 'equipe', provas com 'horario_prova' e 'tipo', resultados com 'posicoes')
    with db_connect() as conn:
        c = conn.cursor()

        # Tabela de usuários (compatível)
        c.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                email TEXT UNIQUE,
                senha_hash TEXT,
                perfil TEXT,
                status TEXT DEFAULT 'Ativo',
                faltas INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de pilotos (legacy format: equipe, status)
        c.execute('''
            CREATE TABLE IF NOT EXISTS pilotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                equipe TEXT,
                status TEXT DEFAULT 'Ativo'
            )
        ''')

        # Tabela de provas (with horario_prova and tipo)
        c.execute('''
            CREATE TABLE IF NOT EXISTS provas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                data TEXT,
                horario_prova TEXT,
                status TEXT DEFAULT 'Ativo',
                tipo TEXT DEFAULT 'Normal'
            )
        ''')

        # Tabela de apostas (legacy structure used across the UI)
        c.execute('''
            CREATE TABLE IF NOT EXISTS apostas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                prova_id INTEGER,
                data_envio TEXT,
                pilotos TEXT,
                fichas TEXT,
                piloto_11 TEXT,
                nome_prova TEXT,
                automatica INTEGER DEFAULT 0,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY(prova_id) REFERENCES provas(id)
            )
        ''')

        # Tabela de resultados (posicoes como texto serializado)
        c.execute('''
            CREATE TABLE IF NOT EXISTS resultados (
                prova_id INTEGER PRIMARY KEY,
                posicoes TEXT,
                FOREIGN KEY(prova_id) REFERENCES provas(id)
            )
        ''')

        # Tabela de posições por participante (Hall da Fama / histórico)
        c.execute('''
            CREATE TABLE IF NOT EXISTS posicoes_participantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prova_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                posicao INTEGER NOT NULL,
                pontos REAL NOT NULL,
                data_registro TEXT DEFAULT (datetime('now')),
                temporada TEXT,
                UNIQUE(prova_id, usuario_id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (prova_id) REFERENCES provas(id)
            )
        ''')

        # Tabela de log de tentativas de login (para rate limiting)
        c.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                tentativa_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sucesso BOOLEAN DEFAULT 0,
                ip_address TEXT
            )
        ''')

        conn.commit()
        logger.info("✓ Banco de dados inicializado com sucesso")

# ============ OPERAÇÕES CRUD ============

def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Retorna usuário pelo email
    
    Args:
        email: Email do usuário
    
    Returns:
        Dict com dados do usuário ou None
    """
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM usuarios WHERE email = ?', (email,))
        row = c.fetchone()
        
        if row:
            return dict(row)
        return None

def get_master_user() -> Optional[Dict]:
    """Retorna o usuário Master se existir"""
    return get_user_by_email('master@sistema.local')

def cadastrar_usuario(nome: str, email: str, senha: str, perfil: str = "participante"):
    """Registra novo usuário com senha bcrypt"""
    senha_hash = hash_password(senha)
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            'INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?)',
            (nome, email, senha_hash, perfil)
        )
        conn.commit()
        logger.info(f"✓ Usuário cadastrado: {email}")

def autenticar_usuario(email: str, senha: str) -> dict:
    """Autentica usuário com bcrypt"""
    usuario = get_user_by_email(email)
    if usuario and check_password(senha, usuario.get('senha_hash', '')):
        return usuario
    return {}

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """
    Retorna usuário pelo ID
    
    Args:
        user_id: ID do usuário
    
    Returns:
        Dict com dados do usuário ou None
    """
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,))
        row = c.fetchone()
        
        if row:
            return dict(row)
        return None

def get_usuarios_df() -> pd.DataFrame:
    """Retorna todos os usuários como DataFrame"""
    with db_connect() as conn:
        return pd.read_sql_query('SELECT * FROM usuarios', conn)

def get_pilotos_df() -> pd.DataFrame:
    """Retorna todos os pilotos como DataFrame"""
    with db_connect() as conn:
        return pd.read_sql_query('SELECT * FROM pilotos', conn)

def _read_table_df(table: str, temporada: Optional[str] = None) -> pd.DataFrame:
    """Helper: read table into DataFrame, filtering by `temporada` when column exists.

    If `temporada` is None, defaults to current year as string.
    Includes NULL temporada rows for backward compatibility with existing data.
    """
    if temporada is None:
        temporada = str(datetime.datetime.now().year)
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(f"PRAGMA table_info('{table}')")
        cols = [r[1] for r in c.fetchall()]
        if 'temporada' in cols:
            # Include rows where temporada matches OR temporada is NULL (backward compat)
            return pd.read_sql_query(f"SELECT * FROM {table} WHERE temporada = ? OR temporada IS NULL", conn, params=(temporada,))
        else:
            return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def get_provas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna todas as provas como DataFrame (filtra por `temporada` quando disponível)."""
    return _read_table_df('provas', temporada)


def get_apostas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna todas as apostas como DataFrame (filtra por `temporada` quando disponível)."""
    return _read_table_df('apostas', temporada)


def get_resultados_df(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna todos os resultados como DataFrame (filtra por `temporada` quando disponível)."""
    return _read_table_df('resultados', temporada)


def registrar_log_aposta(*args, **kwargs):
    """Registro flexível de log de apostas.

    Supports two call patterns for backward compatibility:
    1) registrar_log_aposta(usuario_id, prova_id, piloto_id, pontos=0, temporada=None)
    2) registrar_log_aposta(apostador=..., aposta=..., nome_prova=..., piloto_11=..., tipo_aposta=..., automatica=..., horario=...)

    If pattern (2) is used, entries are stored in an `apostas_log` table (created on demand).
    If pattern (1) is used, an entry is inserted into `apostas` (respecting `temporada` column when present).
    """
    # Pattern 2: verbose logging via kwargs
    if kwargs and ('apostador' in kwargs or 'aposta' in kwargs):
        apostador = kwargs.get('apostador')
        aposta = kwargs.get('aposta')
        nome_prova = kwargs.get('nome_prova')
        piloto_11 = kwargs.get('piloto_11')
        tipo_aposta = kwargs.get('tipo_aposta')
        automatica = kwargs.get('automatica')
        horario = kwargs.get('horario')
        temporada = kwargs.get('temporada', str(datetime.datetime.now().year))

        # Derivar data/horario strings
        data_str = None
        horario_str = None
        try:
            if horario:
                data_str = getattr(horario, 'date', lambda: None)()
                data_str = data_str.isoformat() if data_str else None
                horario_str = horario.isoformat() if hasattr(horario, 'isoformat') else str(horario)
        except Exception:
            data_str = None
            horario_str = None

        with db_connect() as conn:
            c = conn.cursor()
            # create log table if not exists (using log_apostas name for consistency)
            c.execute(f'''
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
                    temporada TEXT DEFAULT '{datetime.datetime.now().year}',
                    status TEXT DEFAULT 'Registrada',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (prova_id) REFERENCES provas(id)
                )
            ''')
            # Check if temporada column exists
            c.execute("PRAGMA table_info('log_apostas')")
            cols = [r[1] for r in c.fetchall()]
            if 'temporada' in cols:
                c.execute(
                    'INSERT INTO log_apostas (apostador, aposta, nome_prova, pilotos, piloto_11, tipo_aposta, automatica, data, horario, temporada) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (apostador, aposta, aposta, piloto_11, piloto_11, tipo_aposta, automatica, data_str, horario_str, temporada)
                )
            else:
                c.execute(
                    'INSERT INTO log_apostas (apostador, aposta, nome_prova, piloto_11, tipo_aposta, automatica, horario) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (apostador, aposta, nome_prova, piloto_11, tipo_aposta, automatica, horario_str)
                )
            conn.commit()
            logger.info(f"✓ Aposta log registrada (log_apostas): {apostador} - {nome_prova}")
        return

    # Pattern 1: positional insert into apostas
    # Normalize args
    usuario_id = None
    prova_id = None
    piloto_id = None
    pontos = 0
    temporada = None
    if len(args) >= 1:
        usuario_id = args[0]
    if len(args) >= 2:
        prova_id = args[1]
    if len(args) >= 3:
        piloto_id = args[2]
    if len(args) >= 4:
        pontos = args[3]
    # kwargs override
    if 'usuario_id' in kwargs:
        usuario_id = kwargs.get('usuario_id')
    if 'prova_id' in kwargs:
        prova_id = kwargs.get('prova_id')
    if 'piloto_id' in kwargs:
        piloto_id = kwargs.get('piloto_id')
    if 'pontos' in kwargs:
        pontos = kwargs.get('pontos')
    if 'temporada' in kwargs:
        temporada = kwargs.get('temporada')

    if temporada is None:
        temporada = str(datetime.datetime.now().year)

    with db_connect() as conn:
        c = conn.cursor()
        # Detect if temporada column exists
        c.execute("PRAGMA table_info('apostas')")
        cols = [r[1] for r in c.fetchall()]
        if 'temporada' in cols:
            c.execute(
                'INSERT INTO apostas (usuario_id, prova_id, piloto_id, pontos, temporada) VALUES (?, ?, ?, ?, ?)',
                (usuario_id, prova_id, piloto_id, pontos, temporada)
            )
        else:
            c.execute(
                'INSERT INTO apostas (usuario_id, prova_id, piloto_id, pontos) VALUES (?, ?, ?, ?)',
                (usuario_id, prova_id, piloto_id, pontos)
            )
        conn.commit()
        logger.info(f"✓ Aposta registrada: usuário {usuario_id}, prova {prova_id}, piloto {piloto_id}")


def log_aposta_existe(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> bool:
    """Verifica se existe aposta para usuário em uma prova (opcionalmente filtrando por temporada)."""
    if temporada is None:
        temporada = str(datetime.datetime.now().year)
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('apostas')")
        cols = [r[1] for r in c.fetchall()]
        if 'temporada' in cols:
            c.execute('SELECT 1 FROM apostas WHERE usuario_id = ? AND prova_id = ? AND temporada = ?', (usuario_id, prova_id, temporada))
        else:
            c.execute('SELECT 1 FROM apostas WHERE usuario_id = ? AND prova_id = ?', (usuario_id, prova_id))
        return c.fetchone() is not None

def update_user_email(user_id: int, novo_email: str) -> bool:
    """Atualiza o email do usuário"""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE usuarios SET email = ? WHERE id = ?', (novo_email, user_id))
            conn.commit()
            logger.info(f"✓ Email do usuário {user_id} atualizado")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar email: {e}")
        return False

def update_user_password(user_id: int, nova_senha: str) -> bool:
    """Atualiza a senha do usuário"""
    try:
        senha_hash = hash_password(nova_senha)
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE usuarios SET senha_hash = ? WHERE id = ?', (senha_hash, user_id))
            conn.commit()
            logger.info(f"✓ Senha do usuário {user_id} atualizada")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar senha: {e}")
        return False

def get_horario_prova(prova_id: int) -> tuple:
    """
    Retorna informações da prova (nome, data, horário)
    
    Args:
        prova_id: ID da prova
    
    Returns:
        Tupla com (nome_prova, data_prova, horario_prova) ou (None, None, None)
    """
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT nome, data FROM provas WHERE id = ?', (prova_id,))
        row = c.fetchone()
        
        if row:
            nome, data = row
            # Retorna nome, data e um horário padrão (00:00)
            return (nome, data, "00:00")
        return (None, None, None)
