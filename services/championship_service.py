import pandas as pd
from datetime import datetime, timezone
from db.db_utils import db_connect

def get_user_name(user_id: int) -> str:
    """Obtém o nome do usuário pelo ID."""
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Nome não encontrado"
    except Exception:
        return "Erro ao buscar nome"

def save_championship_bet(user_id: int, user_nome: str, champion: str, vice: str, team: str) -> bool:
    """Salva ou atualiza a aposta do usuário para o campeonato e registra no log."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT OR REPLACE INTO championship_bets 
            (user_id, user_nome, champion, vice, team, bet_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, user_nome, champion, vice, team, now)
        )
        cursor.execute(
            '''
            INSERT INTO championship_bets_log 
            (user_id, user_nome, champion, vice, team, bet_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, user_nome, champion, vice, team, now)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_championship_bet(user_id: int):
    """Retorna a última aposta válida do usuário no campeonato."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT champion, vice, team, bet_time 
        FROM championship_bets 
        WHERE user_id = ?
        ''', (user_id,)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2], "bet_time": result[3]}
    return None

def get_championship_bet_log(user_id: int):
    """Retorna o histórico de apostas do usuário no campeonato (mais recente primeiro)."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT user_nome, champion, vice, team, bet_time
        FROM championship_bets_log
        WHERE user_id = ?
        ORDER BY bet_time DESC
        ''', (user_id,)
    )
    result = cursor.fetchall()
    conn.close()
    return result

def save_final_results(champion: str, vice: str, team: str, season: int = 2025) -> bool:
    """Salva ou atualiza o resultado oficial do campeonato."""
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT OR REPLACE INTO championship_results 
            (season, champion, vice, team)
            VALUES (?, ?, ?, ?)
            ''', (season, champion, vice, team)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_final_results(season: int = 2025):
    """Retorna o resultado oficial do campeonato."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT champion, vice, team 
        FROM championship_results 
        WHERE season = ?
        ''', (season,)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2]}
    return None

def calcular_pontuacao_campeonato(user_id: int, season: int = 2025) -> int:
    """
    Calcula a pontuação bônus do participante com base nas apostas e no resultado final.
    Retorna o total de pontos extras.
    """
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

def get_championship_bets_df():
    """Retorna todas as apostas de campeonato como DataFrame pandas."""
    conn = db_connect()
    df = pd.read_sql('SELECT * FROM championship_bets', conn)
    conn.close()
    return df

def get_championship_bets_log_df():
    """Retorna o log de apostas de campeonato como DataFrame pandas."""
    conn = db_connect()
    df = pd.read_sql('SELECT * FROM championship_bets_log', conn)
    conn.close()
    return df

def get_championship_results_df():
    """Retorna os resultados oficiais de campeonato como DataFrame pandas."""
    conn = db_connect()
    df = pd.read_sql('SELECT * FROM championship_results', conn)
    conn.close()
    return df
