#!/usr/bin/env python3
"""
Script para importar arquivo SQL no banco de dados SQLite
Uso: python import_sql.py <caminho_para_arquivo.sql>
"""

import sys
import sqlite3
import re
import shutil
from pathlib import Path
from datetime import datetime

def convert_mysql_to_sqlite(sql_content):
    """Converte sintaxe MySQL para SQLite"""
    print("🔄 Convertendo sintaxe MySQL → SQLite...")
    
    # Remover AUTO_INCREMENT
    sql_content = re.sub(r'`(\w+)`\s+integer\s+AUTO_INCREMENT', r'"\1" INTEGER PRIMARY KEY AUTOINCREMENT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'(\w+)\s+integer\s+AUTO_INCREMENT', r'\1 INTEGER PRIMARY KEY AUTOINCREMENT', sql_content, flags=re.IGNORECASE)
    
    # Remover PRIMARY KEY separado
    sql_content = re.sub(r',?\s*PRIMARY KEY\s*\([^)]+\)\s*', '', sql_content, flags=re.IGNORECASE)
    
    # Substituir backticks por aspas duplas
    sql_content = sql_content.replace('`', '"')
    
    # Remover cláusulas MySQL-specific
    sql_content = re.sub(r'\s*ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\s*COLLATE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    
    return sql_content

def import_sql(sql_file, db_path="bolao_f1.db"):
    """Importa arquivo SQL para o banco SQLite"""
    
    if not Path(sql_file).exists():
        print(f"❌ Arquivo não encontrado: {sql_file}")
        return False
    
    print(f"📂 Lendo arquivo: {sql_file}")
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Converter sintaxe
    sql_content = convert_mysql_to_sqlite(sql_content)
    
    # Criar backup do banco atual
    db_path = Path(db_path)
    if db_path.exists():
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_antes_import_{timestamp}.db"
        shutil.copy2(db_path, backup_path)
        print(f"💾 Backup criado: {backup_path}")
        
        # Remover banco atual
        db_path.unlink()
        print(f"🗑️  Banco anterior removido")
    
    # Criar novo banco
    print(f"📥 Importando para: {db_path}")
    conn = sqlite3.connect(str(db_path), timeout=300)
    cursor = conn.cursor()
    
    # Otimizações
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    
    # Separar em comandos
    print("📋 Processando comandos SQL...")
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
    
    total = len(statements)
    print(f"📊 Total de comandos: {total}")
    
    # Executar comandos
    successful = 0
    failed = 0
    
    cursor.execute("BEGIN")
    
    for i, statement in enumerate(statements):
        try:
            cursor.execute(statement)
            successful += 1
            
            # Commit a cada 100 comandos
            if i > 0 and i % 100 == 0:
                conn.commit()
                cursor.execute("BEGIN")
                print(f"⏳ Progresso: {i}/{total} ({int(i/total*100)}%)")
        
        except sqlite3.Error as e:
            failed += 1
            if failed <= 5:
                print(f"⚠️  Erro {failed}: {str(e)[:100]}")
    
    conn.commit()
    
    # Reativar constraints
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("VACUUM")
    
    # Verificar dados importados
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    total_records = 0
    print("\n📊 Tabelas importadas:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        count = cursor.fetchone()[0]
        total_records += count
        print(f"   • {table}: {count} registros")
    
    conn.close()
    
    print("\n" + "="*60)
    print(f"✅ Importação concluída!")
    print(f"   • {len(tables)} tabelas")
    print(f"   • {total_records} registros")
    print(f"   • {successful} comandos executados")
    print(f"   • {failed} erros")
    print("="*60)
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python import_sql.py <arquivo.sql>")
        print("Exemplo: python import_sql.py ~/Downloads/Export.sql")
        sys.exit(1)
    
    sql_file = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "bolao_f1.db"
    
    import_sql(sql_file, db_path)
