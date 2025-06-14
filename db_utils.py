import sqlite3

# Conexão com o banco principal (corridas)
def db_connect():
    return sqlite3.connect('bolao_f1Dev.db', check_same_thread=False)

# Conexão com o banco do campeonato
def championship_db_connect():
    return sqlite3.connect('championship.db', check_same_thread=False)
