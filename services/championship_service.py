import pandas as pd
from datetime import datetime
import logging
from typing import Optional
from db.db_utils import db_connect

logger = logging.getLogger(__name__)

def get_user_name(user_id: int) -> str:
    """Retorna o nome do usuário pelo ID."""
    try:
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (user_id,))
            result = cursor.fetchone()
        return result[0] if result else "Nome não encontrado"
    except Exception as e:
        logger.exception("Erro ao buscar nome do usuário %s: %s", user_id, e)
        return "Nome não encontrado"

def ensure_championship_tables():
    """Garante que as tabelas de campeonato existem."""
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS championship_bets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_nome TEXT NOT NULL,
                champion TEXT NOT NULL,
                vice TEXT NOT NULL,
                team TEXT NOT NULL,
                season INTEGER NOT NULL,
                bet_time TIMESTAMP NOT NULL,
                UNIQUE(user_id, season)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS championship_bets_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_nome TEXT NOT NULL,
                champion TEXT NOT NULL,
                vice TEXT NOT NULL,
                team TEXT NOT NULL,
                season INTEGER NOT NULL,
                bet_time TIMESTAMP NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS championship_results (
                id SERIAL PRIMARY KEY,
                season INTEGER NOT NULL UNIQUE,
                champion TEXT NOT NULL,
                vice TEXT NOT NULL,
                team TEXT NOT NULL
            )
        ''')
        conn.commit()

def save_championship_bet(user_id: int, user_nome: str, champion: str, vice: str, team: str, season: Optional[int] = None) -> bool:
    """Salva ou atualiza a aposta de campeonato do usuário."""
    try:
        season_val = season or datetime.now().year
        now = datetime.now().isoformat()
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO championship_bets 
                (user_id, user_nome, champion, vice, team, season, bet_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, season) DO UPDATE SET
                    user_nome = EXCLUDED.user_nome,
                    champion = EXCLUDED.champion,
                    vice = EXCLUDED.vice,
                    team = EXCLUDED.team,
                    bet_time = EXCLUDED.bet_time
                ''', (user_id, user_nome, champion, vice, team, season_val, now)
            )
            c.execute('''
                INSERT INTO championship_bets_log 
                (user_id, user_nome, champion, vice, team, season, bet_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (user_id, user_nome, champion, vice, team, season_val, now)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("Erro ao salvar aposta de campeonato: %s", e)
        return False

def get_championship_bet(user_id: int, season: Optional[int] = None) -> Optional[dict]:
    """Retorna a aposta de campeonato do usuário para a temporada."""
    try:
        season_val = season or datetime.now().year
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT champion, vice, team, bet_time 
            FROM championship_bets 
            WHERE user_id = %s AND season = %s
            ''', (user_id, season_val)
        )
        result = cursor.fetchone()
        if result:
            return {
                'champion': result[0],
                'vice': result[1],
                'team': result[2],
                'bet_time': result[3]
            }
        return None
    except Exception as e:
        logger.exception("Erro ao buscar aposta de campeonato: %s", e)
        return None

def get_championship_bets_log(user_id: int, season: Optional[int] = None) -> list:
    """Retorna o histórico de apostas de campeonato do usuário."""
    try:
        season_val = season or datetime.now().year
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT user_nome, champion, vice, team, season, bet_time
            FROM championship_bets_log
            WHERE user_id = %s AND season = %s
            ORDER BY bet_time DESC
            ''', (user_id, season_val)
        )
        rows = cursor.fetchall() or []
        return [
            {'user_nome': r[0], 'champion': r[1], 'vice': r[2],
             'team': r[3], 'season': r[4], 'bet_time': r[5]}
            for r in rows
        ]
    except Exception as e:
        logger.exception("Erro ao buscar histórico de apostas: %s", e)
        return []

def save_championship_result(season: int, champion: str, vice: str, team: str) -> bool:
    """Salva ou atualiza o resultado do campeonato."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO championship_results 
                (season, champion, vice, team)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (season) DO UPDATE SET
                    champion = EXCLUDED.champion,
                    vice = EXCLUDED.vice,
                    team = EXCLUDED.team
                ''', (season, champion, vice, team)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("Erro ao salvar resultado do campeonato: %s", e)
        return False

def get_championship_result(season: Optional[int] = None) -> Optional[dict]:
    """Retorna o resultado do campeonato para a temporada."""
    try:
        season_val = season or datetime.now().year
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT champion, vice, team 
            FROM championship_results 
            WHERE season = %s
            ''', (season_val,)
        )
        result = cursor.fetchone()
        if result:
            return {'champion': result[0], 'vice': result[1], 'team': result[2]}
        return None
    except Exception as e:
        logger.exception("Erro ao buscar resultado do campeonato: %s", e)
        return None

def get_championship_bets_df(season: Optional[int] = None) -> pd.DataFrame:
    """Retorna DataFrame com todas as apostas de campeonato."""
    try:
        with db_connect() as conn:
            if season is None:
                df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets', conn)
            else:
                df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets WHERE season = %s', conn, params=(season,))
        return df
    except Exception as e:
        logger.exception("Erro ao buscar apostas: %s", e)
        return pd.DataFrame()

def get_championship_bets_log_df(season: Optional[int] = None):
    """Retorna DataFrame com o log de apostas."""
    try:
        with db_connect() as conn:
            if season is None:
                df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log', conn)
            else:
                df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log WHERE season = %s', conn, params=(season,))
        return df
    except Exception as e:
        logger.exception("Erro ao buscar log de apostas: %s", e)
        return pd.DataFrame()

def get_championship_results_df(season: Optional[int] = None) -> pd.DataFrame:
    """Retorna DataFrame com os resultados do campeonato."""
    try:
        with db_connect() as conn:
            if season is None:
                df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results', conn)
            else:
                df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results WHERE season = %s', conn, params=(season,))
        return df
    except Exception as e:
        logger.exception("Erro ao buscar resultados: %s", e)
        return pd.DataFrame()
