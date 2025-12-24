"""
Pool de Conexões SQLite para Melhor Performance
Reduz overhead de conexões frequentes ao banco de dados
"""

import sqlite3
from pathlib import Path
from typing import Optional
import threading
from contextlib import contextmanager

class ConnectionPool:
    """
    Pool de Conexões Thread-Safe para SQLite
    
    Uso:
        pool = ConnectionPool("banco.db", pool_size=5)
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios")
    """
    
    def __init__(self, db_path: str, pool_size: int = 5, timeout: float = 30.0):
        """
        Inicializa o pool de conexões
        
        Args:
            db_path: Caminho do arquivo SQLite
            pool_size: Número máximo de conexões no pool
            timeout: Timeout para operações (segundos)
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._connections: list = []
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(pool_size)
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Cria as conexões iniciais"""
        with self._lock:
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._connections.append(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """Cria uma nova conexão com SQLite"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging para melhor concorrência
        conn.execute("PRAGMA synchronous=NORMAL")  # Menos lento que FULL, mais seguro que OFF
        conn.execute("PRAGMA cache_size=-64000")  # 64MB de cache
        return conn
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obter uma conexão do pool
        
        Exemplo:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                ...
        """
        self._semaphore.acquire()
        conn = None
        try:
            with self._lock:
                if self._connections:
                    conn = self._connections.pop()
            
            if conn is None:
                conn = self._create_connection()
            
            yield conn
            
        finally:
            if conn:
                with self._lock:
                    if len(self._connections) < self.pool_size:
                        self._connections.append(conn)
                    else:
                        conn.close()
            self._semaphore.release()
    
    def close_all(self):
        """Fecha todas as conexões do pool"""
        with self._lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()


# Instância global do pool
_pool: Optional[ConnectionPool] = None

def init_pool(db_path: str = "bolao_f1.db", pool_size: int = 5):
    """Inicializa o pool global"""
    global _pool
    _pool = ConnectionPool(db_path, pool_size)

def get_pool() -> ConnectionPool:
    """Retorna o pool global"""
    if _pool is None:
        # Importar aqui para evitar circular import
        from db.db_config import DB_PATH
        init_pool(str(DB_PATH))
    return _pool

def close_pool():
    """Fecha o pool global"""
    global _pool
    if _pool:
        _pool.close_all()
        _pool = None
