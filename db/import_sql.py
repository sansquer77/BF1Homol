"""
Importador de SQL compatível com dumps MySQL/SQLite
Converte automaticamente sintaxe MySQL para SQLite
Corrigido para tratar corretamente o WAL (Write-Ahead Log)
"""

import sqlite3
import re
from pathlib import Path
from db.db_config import DB_PATH
from db.connection_pool import close_pool, init_pool


def convert_mysql_to_sqlite(sql_content):
    """Converte sintaxe MySQL para SQLite"""

    # Remover AUTO_INCREMENT
    sql_content = re.sub(r'\s+AUTO_INCREMENT\s*,', ',', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\s+AUTO_INCREMENT\s+', ' ', sql_content, flags=re.IGNORECASE)

    # Substituir AUTOINCREMENT por AUTOINCREMENT (SQLite exige maiúscula)
    sql_content = re.sub(r'integer\s+AUTO_INCREMENT', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql_content, flags=re.IGNORECASE)

    # Remover backticks e substituir por aspas duplas
    sql_content = sql_content.replace('`', '"')

    # Remover ENGINE=InnoDB, CHARSET, etc
    sql_content = re.sub(r'\s*ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\s*COLLATE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)

    # Garantir que PRIMARY KEY está na definição correta
    sql_content = re.sub(r'(\s+id\s+)integer\s*,\s*PRIMARY KEY\s*\(\s*id\s*\)', r'\1INTEGER PRIMARY KEY AUTOINCREMENT', sql_content, flags=re.IGNORECASE)

    return sql_content


def import_sql_file(sql_file_path, target_db_path=None):
    """
    Importa arquivo SQL convertendo MySQL->SQLite se necessario.
    Usa DELETE mode em vez de WAL para garantir que os dados sejam
    escritos diretamente no arquivo .db.

    Args:
        sql_file_path: Caminho do arquivo .sql
        target_db_path: Caminho do banco destino (default: DB_PATH)

    Returns:
        tuple: (success: bool, message: str, stats: dict)
    """
    if target_db_path is None:
        target_db_path = DB_PATH

    # Fechar pool para evitar locks SQLite durante importacao
    close_pool()

    try:
        # Ler arquivo SQL
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Converter sintaxe
        sql_content = convert_mysql_to_sqlite(sql_content)

        # Separar em comandos
        statements = []
        current_statement = []

        for line in sql_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('--'):
                continue
            current_statement.append(line)
            if line.endswith(';'):
                statements.append(' '.join(current_statement))
                current_statement = []

        # Conectar e executar - usar DELETE mode para evitar problemas com WAL
        conn = sqlite3.connect(str(target_db_path), timeout=30, isolation_level=None)
        cursor = conn.cursor()

        # CRÍTICO: Usar DELETE mode em vez de WAL para garantir escrita direta
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("PRAGMA synchronous=FULL")

        stats = {
            'total_statements': len(statements),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        # Iniciar transacao explicita
        cursor.execute("BEGIN TRANSACTION")

        for i, statement in enumerate(statements):
            try:
                cursor.execute(statement)
                stats['successful'] += 1

                # Commit periodico a cada 100 comandos
                if (i + 1) % 100 == 0:
                    conn.commit()
                    cursor.execute("BEGIN TRANSACTION")

            except sqlite3.Error as e:
                stats['failed'] += 1
                stats['errors'].append(f"Erro: {str(e)[:100]} | SQL: {statement[:100]}")

        # Commit final garantido
        conn.commit()

        # Reabilitar configuracoes normais
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # CRÍTICO: Consolidar WAL se existir e fazer VACUUM
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cursor.execute("VACUUM")
        
        conn.close()
        
        # Remover arquivos WAL/SHM que podem ter sido criados
        target_path = Path(target_db_path)
        wal_file = Path(str(target_path) + "-wal")
        shm_file = Path(str(target_path) + "-shm")
        if wal_file.exists():
            wal_file.unlink()
        if shm_file.exists():
            shm_file.unlink()

        # Reinicializar pool apos importacao
        init_pool()

        return (True, f"✅ Importacao concluida: {stats['successful']} comandos executados, {stats['failed']} erros", stats)

    except Exception as e:
        # Reinicializar pool mesmo em caso de erro
        init_pool()
        return (False, f"❌ Erro ao importar SQL: {str(e)}", {})

if __name__ == "__main__":
    # Teste
    import sys
    if len(sys.argv) > 1:
        success, msg, stats = import_sql_file(sys.argv[1])
        print(msg)
        if stats.get('errors'):
            print("\nErros encontrados:")
            for err in stats['errors'][:10]:
                print(err)
