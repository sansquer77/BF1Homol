import pandas as pd
import logging
from datetime import datetime, timedelta
import html
from typing import Optional
from db.db_utils import db_connect, get_user_by_id, get_provas_df
from services.rules_service import get_regras_aplicaveis
from services.email_service import enviar_email, gerar_analise_aposta_com_probabilidade
from utils.datetime_utils import SAO_PAULO_TZ, now_sao_paulo, normalize_time_string, parse_datetime_sao_paulo

logger = logging.getLogger(__name__)


def _season_or_current(season: Optional[int]) -> int:
    """Retorna a temporada fornecida ou o ano corrente."""
    return season if season is not None else datetime.now().year

def _parse_datetime_sp(date_str: str, time_str: str) -> datetime:
    """Parseia data/hora e retorna datetime com timezone America/Sao_Paulo."""
    return parse_datetime_sao_paulo(date_str, time_str)

def can_place_championship_bet(season: Optional[int] = None, now: Optional[datetime] = None) -> tuple[bool, str, Optional[datetime]]:
    """Valida se apostas do campeonato estao abertas para a temporada.

    Regra: bloqueia a partir de 1 minuto apos o horario da primeira prova.
    Retorna (pode, mensagem, deadline_sp).
    """
    season_val = _season_or_current(season)
    current_season = datetime.now().year
    if season_val < current_season:
        return False, f"Apostas bloqueadas para temporada encerrada ({season_val}).", None

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
            normalized_time = normalize_time_string(horario_str)
            try:
                if normalized_time in ("00:00", "00:00:00", None):
                    dt_list_fallback.append(_parse_datetime_sp(data_str, "00:00:00"))
                else:
                    dt_list.append(_parse_datetime_sp(data_str, horario_str))
            except ValueError:
                continue

        if not dt_list and dt_list_fallback:
            dt_list = dt_list_fallback

        if not dt_list:
            return True, "Nao foi possivel calcular o prazo; apostas liberadas.", None

        primeira_prova = min(dt_list)
        deadline = primeira_prova + timedelta(minutes=1)

        now_sp = now or now_sao_paulo()
        if now_sp.tzinfo is None:
            now_sp = now_sp.replace(tzinfo=SAO_PAULO_TZ)

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

def save_championship_bet(user_id: int, user_nome: str, champion: str, vice: str, team: str, season: Optional[int] = None) -> bool:
    """Salva ou atualiza a aposta do usuário para o campeonato e registra no log, por temporada."""
    now_sp = now_sao_paulo()
    now = now_sp.strftime("%Y-%m-%d %H:%M:%S")
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

        try:
            analise = gerar_analise_aposta_com_probabilidade(
                nome_usuario=user_nome,
                contexto_aposta=f"Campeonato F1 {season_val}",
                detalhes_aposta=f"Campeão: {champion}; Vice: {vice}; Equipe campeã: {team}",
            )
            comentario = str(analise.get("comentario", "")).strip()
            probabilidade = analise.get("probabilidade")
            resumo = str(analise.get("resumo", "")).strip()

            bloco_analise = ""
            if comentario:
                bloco_analise += "<p><b>Comentário sarcástico:</b><br>" + "<br>".join(html.escape(comentario).splitlines()) + "</p>"
            if probabilidade is not None:
                bloco_analise += f"<p><b>Probabilidade estimada de acerto:</b> {int(probabilidade)}%</p>"
            if resumo:
                bloco_analise += "<p><b>Base da estimativa:</b> " + html.escape(resumo) + "</p>"

            corpo_email = (
                f"<p>Olá {html.escape(user_nome)},</p>"
                f"<p>Sua aposta do campeonato <b>{season_val}</b> foi registrada com sucesso.</p>"
                "<p><b>Detalhes:</b></p>"
                "<ul>"
                f"<li>Campeão: {html.escape(champion)}</li>"
                f"<li>Vice-campeão: {html.escape(vice)}</li>"
                f"<li>Equipe campeã: {html.escape(team)}</li>"
                f"<li>Data/Hora do registro (Brasília): {html.escape(now)}</li>"
                "</ul>"
                f"{bloco_analise}"
                "<p><small><b>Aviso de estimativa:</b> a probabilidade informada é apenas uma projeção estatística/opinativa com base em informações disponíveis e pode variar a qualquer momento. Não constitui garantia de resultado esportivo nem direito a pontuação, prevalecendo sempre as regras oficiais do bolão.</small></p>"
                "<p>Boa sorte!</p>"
            )
            email_ok = enviar_email(usuario.get('email', ''), f"Aposta de campeonato registrada - {season_val}", corpo_email)
            if not email_ok:
                logger.warning(
                    "Email de confirmação da aposta de campeonato não foi enviado (user_id=%s, season=%s)",
                    user_id,
                    season_val,
                )
        except Exception as mail_error:
            logger.warning(f"Falha ao enviar email de confirmação da aposta de campeonato (user_id={user_id}): {mail_error}")
        return True
    except Exception as e:
        logger.exception(f"Erro ao salvar aposta de campeonato (user_id={user_id}, season={season_val}): {e}")
        return False

def get_championship_bet(user_id: int, season: Optional[int] = None):
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

def get_championship_bet_log(user_id: int, season: Optional[int] = None):
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

def save_final_results(champion: str, vice: str, team: str, season: Optional[int] = None) -> bool:
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

def get_final_results(season: Optional[int] = None):
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

def calcular_pontuacao_campeonato(user_id: int, season: Optional[int] = None) -> int:
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

def get_championship_bets_df(season: Optional[int] = None):
    """Retorna apostas de campeonato; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets', conn)
        else:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets WHERE season = ?', conn, params=(season,))
    return df

def get_championship_bets_log_df(season: Optional[int] = None):
    """Retorna log de apostas; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log', conn)
        else:
            df = pd.read_sql('SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log WHERE season = ?', conn, params=(season,))
    return df

def get_championship_results_df(season: Optional[int] = None):
    """Retorna resultados oficiais; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results', conn)
        else:
            df = pd.read_sql('SELECT season, champion, vice, team FROM championship_results WHERE season = ?', conn, params=(season,))
    return df
