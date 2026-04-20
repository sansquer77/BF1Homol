import pandas as pd
import logging
from datetime import datetime, timedelta
import html
from typing import Optional
from db.db_schema import db_connect
from db.repo_users import get_user_by_id
from db.repo_races import get_provas_df
from services.rules_service import get_regras_aplicaveis
from utils.helpers import get_bf1_logo_data_uri
from services.email_service import enviar_email, gerar_analise_aposta_com_probabilidade
from utils.datetime_utils import SAO_PAULO_TZ, now_sao_paulo, normalize_time_string, parse_datetime_sao_paulo
from utils.input_models import ChampionshipBetInput, ChampionshipResultInput, ValidationError

logger = logging.getLogger(__name__)


def _fetch_df(conn, query: str, params: tuple | None = None) -> pd.DataFrame:
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    rows = cursor.fetchall() or []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


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
            cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (user_id,))
            result = cursor.fetchone()
        return result['nome'] if result else "Nome não encontrado"
    except Exception as e:
        logger.exception(f"Erro ao buscar nome do usuário {user_id}: {e}")
        return "Erro ao buscar nome"

def save_championship_bet(user_id: int, user_nome: str, champion: str, vice: str, team: str, season: Optional[int] = None) -> bool:
    """Salva ou atualiza a aposta do usuário para o campeonato e registra no log, por temporada."""
    try:
        payload = ChampionshipBetInput(
            user_id=user_id,
            user_nome=user_nome,
            champion=champion,
            vice=vice,
            team=team,
            season=season,
        )
        user_id = payload.user_id
        user_nome = payload.user_nome
        champion = payload.champion
        vice = payload.vice
        team = payload.team
        season = payload.season
    except ValidationError as exc:
        logger.warning("Aposta de campeonato rejeitada por validacao: %s", exc)
        return False

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
            cursor.execute(
                '''
                INSERT INTO championship_bets_log
                (user_id, user_nome, champion, vice, team, season, bet_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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

            # Obter logo BF1 como data URI para embutir no email
            bf1_logo_uri = get_bf1_logo_data_uri()

            corpo_email = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confirmação de Aposta de Campeonato BF1</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            background-color: #ffffff;
            text-align: center;
            padding: 20px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .logo {{
            width: 100px;
            height: auto;
            margin: 0;
        }}
        .content {{
            padding: 30px;
            color: #333333;
        }}
        .greeting {{
            font-size: 18px;
            margin-bottom: 20px;
        }}
        .success-message {{
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .details-box {{
            background-color: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 20px;
            margin: 20px 0;
        }}
        .details-box h3 {{
            margin-top: 0;
            color: #d32f2f;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: bold;
            color: #555;
        }}
        .detail-value {{
            color: #333;
            text-align: right;
        }}
        .analysis-box {{
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .analysis-box h4 {{
            margin-top: 0;
            color: #f57c00;
        }}
        .message {{
            font-size: 16px;
            line-height: 1.6;
            margin: 15px 0;
        }}
        .footer {{
            background-color: #f5f5f5;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666666;
            border-top: 1px solid #e0e0e0;
        }}
        .disclaimer {{
            font-size: 12px;
            color: #999;
            margin-top: 15px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{bf1_logo_uri}" alt="BF1 Logo" class="logo">
        </div>
        <div class="content">
            <p class="greeting">Olá {html.escape(user_nome)},</p>
            <div class="success-message">
                <strong>✓ Aposta de campeonato registrada com sucesso!</strong> Sua aposta para a temporada <strong>{season_val}</strong> foi confirmada no sistema.
            </div>
            <div class="details-box">
                <h3>Detalhes da Aposta</h3>
                <div class="detail-row">
                    <span class="detail-label">Temporada:</span>
                    <span class="detail-value">{season_val}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Campeão:</span>
                    <span class="detail-value">{html.escape(champion)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Vice-campeão:</span>
                    <span class="detail-value">{html.escape(vice)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Equipe campeã:</span>
                    <span class="detail-value">{html.escape(team)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Data/Hora do registro (Brasília):</span>
                    <span class="detail-value">{html.escape(now)}</span>
                </div>
            </div>
            {f'''<div class="analysis-box">
                <h4>📊 Análise da Aposta</h4>
                {bloco_analise}
            </div>''' if bloco_analise else ''}
            <p class="message">Boa sorte na temporada! Você pode revisar ou modificar sua aposta de campeonato a qualquer momento acessando sua conta no sistema.</p>
            <p class="disclaimer"><strong>⚠️ Aviso de estimativa:</strong> a probabilidade informada é apenas uma projeção estatística/opinativa com base em informações disponíveis e pode variar a qualquer momento. Não constitui garantia de resultado esportivo nem direito a pontuação, prevalecendo sempre as regras oficiais do bolão.</p>
        </div>
        <div class="footer">
            <p>Equipe de Organização BF1</p>
            <p>Este é um alerta automático do sistema de gerenciamento do bolão.</p>
        </div>
    </div>
</body>
</html>
"""
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
            WHERE user_id = %s AND season = %s
            ''', (user_id, season_val)
        )
        result = cursor.fetchone()
    if result:
        return {"champion": result['champion'], "vice": result['vice'], "team": result['team'], "bet_time": result['bet_time']}
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
            WHERE user_id = %s AND season = %s
            ORDER BY bet_time DESC
            ''', (user_id, season_val)
        )
        result = cursor.fetchall()
    return result

def save_final_results(champion: str, vice: str, team: str, season: Optional[int] = None) -> bool:
    """Salva ou atualiza o resultado oficial do campeonato por temporada."""
    try:
        payload = ChampionshipResultInput(
            champion=champion,
            vice=vice,
            team=team,
            season=season,
        )
        champion = payload.champion
        vice = payload.vice
        team = payload.team
        season = payload.season
    except ValidationError as exc:
        logger.warning("Resultado de campeonato rejeitado por validacao: %s", exc)
        return False

    season_val = _season_or_current(season)
    try:
        with db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO championship_results
                (season, champion, vice, team)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (season) DO UPDATE SET
                    champion = EXCLUDED.champion,
                    vice = EXCLUDED.vice,
                    team = EXCLUDED.team
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
            WHERE season = %s
            ''', (season_val,)
        )
        result = cursor.fetchone()
    if result:
        return {"champion": result['champion'], "vice": result['vice'], "team": result['team']}
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
            df = _fetch_df(conn, 'SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets')
        else:
            df = _fetch_df(conn, 'SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets WHERE season = %s', (season,))
    return df

def get_championship_bets_log_df(season: Optional[int] = None):
    """Retorna log de apostas; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = _fetch_df(conn, 'SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log')
        else:
            df = _fetch_df(conn, 'SELECT user_id, user_nome, champion, vice, team, season, bet_time FROM championship_bets_log WHERE season = %s', (season,))
    return df

def get_championship_results_df(season: Optional[int] = None):
    """Retorna resultados oficiais; se season informado, filtra."""
    with db_connect() as conn:
        if season is None:
            df = _fetch_df(conn, 'SELECT season, champion, vice, team FROM championship_results')
        else:
            df = _fetch_df(conn, 'SELECT season, champion, vice, team FROM championship_results WHERE season = %s', (season,))
    return df
