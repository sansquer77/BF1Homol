import pandas as pd
import logging
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from db.db_utils import db_connect, get_user_by_id, get_provas_df
from services.rules_service import get_regras_aplicaveis

logger = logging.getLogger(__name__)


def _season_or_current(season: int | None) -> int:
    """Retorna a temporada fornecida ou o ano corrente."""
    return season if season is not None else datetime.now().year

def _normalize_time_str(time_str: str | None) -> str | None:
    if not time_str:
        return None
    raw = str(time_str).strip().lower()
    if not raw:
        return None
    raw = raw.replace("h", ":")
    match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", raw)
    if not match:
        return None
    value = match.group(1)
    parts = value.split(":")
    if len(parts[0]) == 1:
        parts[0] = parts[0].zfill(2)
    return ":".join(parts)

def _parse_datetime_sp(date_str: str, time_str: str) -> datetime:
    """Parseia data/hora e retorna datetime com timezone America/Sao_Paulo."""
    normalized_time = _normalize_time_str(time_str)
    if not normalized_time:
        raise ValueError(f"Formato de hora invalido: '{time_str}'")
    fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(f"{date_str} {normalized_time}", fmt)
            return dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        except ValueError:
            continue
    raise ValueError(f"Formato de data/hora invalido: '{date_str} {normalized_time}'")

def can_place_championship_bet(season: int | None = None, now: datetime | None = None) -> tuple[bool, str, datetime | None]:
    """Valida se apostas do campeonato estao abertas para a temporada.

    Regra: bloqueia a partir de 1 minuto apos o horario da primeira prova.
    Retorna (pode, mensagem, deadline_sp).
    """
    season_val = _season_or_current(season)
    try:
        provas_df = get_provas_df(str(season_val))
        if provas_df.empty:
            return True, "Sem provas cadastradas; apostas liberadas.", None

        if "status" in provas_df.columns:
            provas_df = provas_df[provas_df["status"].fillna("").str.lower() != "inativa"]
            if provas_df.empty:
                return True, "Sem provas ativas; apostas liberadas.", None

        dt_list = []
        dt_list_fallback = []
        for _, row in provas_df.iterrows():
            data_str = str(row.get("data", "")).strip()
            horario_raw = row.get("horario_prova")
            horario_str = str(horario_raw or "").strip()
            if not data_str:
                continue
            normalized_time = _normalize_time_str(horario_str)
            try:
                if normalized_time in ("00:00", "00:00:00", None):
                    dt_list_fallback.append(_parse_datetime_sp(data_str, "00:00:00"))
                else:
                    dt_list.append(_parse_datetime_sp(data_str, horario_str))
            except Exception:
                continue

        if not dt_list and dt_list_fallback:
            dt_list = dt_list_fallback

        if not dt_list:
            return True, "Nao foi possivel calcular o prazo; apostas liberadas.", None

        primeira_prova = min(dt_list)
        deadline = primeira_prova + timedelta(minutes=1)

        now_sp = now or datetime.now(ZoneInfo("America/Sao_Paulo"))
        if now_sp.tzinfo is None:
            now_sp = now_sp.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

        if now_sp > deadline:
            msg = f"Apostas bloqueadas. Prazo encerrou em {deadline.strftime('%d/%m/%Y %H:%M:%S')} (SP)."
            return False, msg, deadline

        msg = f"Apostas liberadas ate {deadline.strftime('%d/%m/%Y %H:%M:%S')} (SP)."
        return True, msg, deadline
    except Exception as e:
        logger.exception(f"Erro ao validar prazo de aposta do campeonato (season={season_val}): {e}")
        return True, "Erro ao validar prazo; apostas liberadas.", None

def get_user_name(user_id: int) -> str:
    """Obtém o nome do usuário pelo ID."""
    try:
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (user_id,))
            result = cursor.fetchone()
        return result[0] if result else "Nome não encontrado"
    except Exception as e:
        logger.exception(f"Erro ao buscar nome do usuário {user_id}: {e}")
        return "Erro ao buscar nome"

def save_championship_bet(user_id: int, user_nome: str, champion: str, vice: str, team: str, season: int | None = None) -> bool:
    """Salva ou atualiza a aposta do usuário para o campeonato e registra no log, por temporada."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    season_val = _season_or_current(season)
    try:
        pode, _, _ = can_place_championship_bet(season_val)
        if not pode:
            return False
        usuario = get_user_by_id(user_id)
        if not usuario:
            return False
        status_usuario = str(usuario.get('status', '')).strip().lower()
        if status_usuario and status_usuario != 'ativo':
            return False
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT OR REPLACE INTO championship_bets 
                (user_id, user_nome, champion, vice, team, season, bet_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, user_nome, champion, vice, team, season_val, now)
            )
            cursor.execute(
                '''
                INSERT INTO championship_bets_log 
                (user_id, user_nome, champion, vice, team, season, bet_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, user_nome, champion, vice, team, season_val, now)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception(f"Erro ao salvar aposta de campeonato (user_id={user_id}, season={season_val}): {e}")
        return False

def get_championship_bet(user_id: int, season: int | None = None):
    """Retorna a última aposta válida do usuário no campeonato para a temporada informada."""
    season_val = _season_or_current(season)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT champion, vice, team, bet_time 
            FROM championship_bets 
            WHERE user_id = ? AND season = ?
            ''', (user_id, season_val)
        )
        result = cursor.fetchone()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2], "bet_time": result[3]}
    return None

def get_championship_bet_log(user_id: int, season: int | None = None):
    """Retorna o histórico de apostas do usuário no campeonato (mais recente primeiro) para a temporada."""
    season_val = _season_or_current(season)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT user_nome, champion, vice, team, season, bet_time
            FROM championship_bets_log
            WHERE user_id = ? AND season = ?
            ORDER BY bet_time DESC
            ''', (user_id, season_val)
        )
        result = cursor.fetchall()
    return result

def save_final_results(champion: str, vice: str, team: str, season: int | None = None) -> bool:
    """Salva ou atualiza o resultado oficial do campeonato por temporada."""
    season_val = _season_or_current(season)
    try:
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT OR REPLACE INTO championship_results 
                (season, champion, vice, team)
                VALUES (?, ?, ?, ?)
                ''', (season_val, champion, vice, team)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception(f"Erro ao salvar resultado final do campeonato (season={season_val}): {e}")
        return False

def get_final_results(season: int | None = None):
    """Retorna o resultado oficial do campeonato para a temporada informada."""
    season_val = _season_or_current(season)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT champion, vice, team 
            FROM championship_results 
            WHERE season = ?
            ''', (season_val,)
        )
        result = cursor.fetchone()
    if result:
        return {"champion": result[0], "vice": result[1], "team": result[2]}
    return None

def calcular_pontuacao_campeonato(user_id: int, season: int | None = None) -> int:
    """Calcula pontos bônus do participante considerando a temporada informada."""
    season_val = _season_or_current(season)
    aposta = get_championship_bet(user_id, season_val)
    resultado = get_final_results(season_val)
    regras = get_regras_aplicaveis(str(season_val), "Normal")
    pontos_campeao = regras.get('pontos_campeao', 150)
    pontos_vice = regras.get('pontos_vice', 100)
    pontos_equipe = regras.get('pontos_equipe', 80)
    pontos = 0
    if aposta and resultado:
        if aposta["champion"] == resultado["champion"]:
            pontos += pontos_campeao
        if aposta["vice"] == resultado["vice"]:
            pontos += pontos_vice
        if aposta["team"] == resultado["team"]:
            pontos += pontos_equipe
    return pontos

def get_championship_bets_df(season: int | None = None):
    """Retorna apostas de campeonato; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets', conn)
        else:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets WHERE season = ?', conn, params=(season,))
    return df

def get_championship_bets_log_df(season: int | None = None):
    """Retorna log de apostas; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log', conn)
        else:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log WHERE season = ?', conn, params=(season,))
    return df

def get_championship_results_df(season: int | None = None):
    """Retorna resultados oficiais; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results', conn)
        else:
            df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results WHERE season = ?', conn, params=(season,))
    return df
