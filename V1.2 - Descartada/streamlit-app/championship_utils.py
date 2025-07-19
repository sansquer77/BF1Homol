import pandas as pd
from db_utils import championship_db_connect, db_connect
from datetime import datetime, UTC

def init_championship_db():
    """Cria as tabelas necessárias para apostas e resultado do campeonato."""
    conn = championship_db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS championship_bets (
            user_id INTEGER PRIMARY KEY,
            user_nome TEXT NOT NULL,
            champion TEXT NOT NULL,
            vice TEXT NOT NULL,
            team TEXT NOT NULL,
            bet_time TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS championship_bets_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_nome TEXT NOT NULL,
            champion TEXT NOT NULL,
            vice TEXT NOT NULL,
            team TEXT NOT NULL,
            bet_time TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS championship_results (
            season INTEGER PRIMARY KEY DEFAULT 2025,
            champion TEXT NOT NULL,
            vice TEXT NOT NULL,
            team TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_user_name(user_id):
    """Obtém o nome do usuário pelo ID"""
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Nome não encontrado"
    except Exception:
        return "Erro ao buscar nome"

def save_championship_bet(user_id, user_nome, champion, vice, team):
    """Salva ou atualiza a aposta do usuário para o campeonato e registra no log."""
    init_championship_db()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    conn = championship_db_connect()
    cursor = conn.cursor()
    # Atualiza aposta válida (última)
    cursor.execute('''
        INSERT OR REPLACE INTO championship_bets (user_id, user_nome, champion, vice, team, bet_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_nome, champion, vice, team, now))
    # Registra log de apostas
    cursor.execute('''
        INSERT INTO championship_bets_log (user_id, user_nome, champion, vice, team, bet_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_nome, champion, vice, team, now))
    conn.commit()
    conn.close()

def get_championship_bet(user_id):
    """Retorna a última aposta válida do usuário no campeonato."""
    init_championship_db()
    conn = championship_db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT champion, vice, team, bet_time FROM championship_bets WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2], "bet_time": result[3]}
    return None

def get_championship_bet_log(user_id):
    """Retorna o histórico de apostas do usuário no campeonato (mais recente primeiro)."""
    init_championship_db()
    conn = championship_db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_nome, champion, vice, team, bet_time
        FROM championship_bets_log
        WHERE user_id = ?
        ORDER BY bet_time DESC
    ''', (user_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def save_final_results(champion, vice, team, season=2025):
    """Salva ou atualiza o resultado oficial do campeonato."""
    init_championship_db()
    conn = championship_db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO championship_results (season, champion, vice, team)
        VALUES (?, ?, ?, ?)
    ''', (season, champion, vice, team))
    conn.commit()
    conn.close()

def get_final_results(season=2025):
    """Retorna o resultado oficial do campeonato."""
    init_championship_db()
    conn = championship_db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT champion, vice, team FROM championship_results WHERE season = ?
    ''', (season,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2]}
    return None

def calcular_pontuacao_campeonato(user_id, season=2025):
    """Calcula a pontuação bônus do participante com base nas apostas e resultado final."""
    aposta = get_championship_bet(user_id)
    resultado = get_final_results(season)
    pontos = 0
    if aposta and resultado:
        if aposta["champion"] == resultado["champion"]:
            pontos += 150
        if aposta["vice"] == resultado["vice"]:
            pontos += 100
        if aposta["team"] == resultado["team"]:
            pontos += 80
    return pontos
