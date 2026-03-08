import pandas as pd
import streamlit as st
import logging
import os
import json
import ast
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from db.db_utils import (
    get_user_by_id,
    get_horario_prova,
    db_connect,
    get_pilotos_df,
    registrar_log_aposta,
    log_aposta_existe,
    get_apostas_df,
    get_provas_df,
    get_resultados_df
)
from services.email_service import enviar_email, gerar_analise_aposta_com_probabilidade
import html
from services.rules_service import get_regras_aplicaveis
from utils.datetime_utils import SAO_PAULO_TZ, now_sao_paulo, parse_datetime_sao_paulo

logger = logging.getLogger(__name__)


def _extrair_json_texto(raw_text: str) -> dict | None:
    if not raw_text:
        return None
    txt = raw_text.strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    ini = txt.find('{')
    fim = txt.rfind('}')
    if ini == -1 or fim == -1 or fim <= ini:
        return None
    try:
        return json.loads(txt[ini:fim + 1])
    except Exception:
        return None


def _aposta_valida_regras(pilotos_sel: list[str], fichas_sel: list[int], piloto_11: str, pilotos_df: pd.DataFrame, regras: dict) -> bool:
    if not pilotos_sel or not fichas_sel or not piloto_11:
        return False

    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

    if len(pilotos_sel) < min_pilotos:
        return False
    if len(pilotos_sel) != len(fichas_sel):
        return False
    if len(set(pilotos_sel)) != len(pilotos_sel):
        return False
    if sum(int(f) for f in fichas_sel) != qtd_fichas:
        return False
    if fichas_sel and max(int(f) for f in fichas_sel) > fichas_max:
        return False
    if piloto_11 in pilotos_sel:
        return False

    pilotos_disponiveis = set(pilotos_df['nome'].astype(str).tolist()) if not pilotos_df.empty else set()
    if pilotos_disponiveis and any(str(p) not in pilotos_disponiveis for p in pilotos_sel):
        return False
    if pilotos_disponiveis and str(piloto_11) not in pilotos_disponiveis:
        return False

    if not permite_mesma_equipe and not pilotos_df.empty and 'equipe' in pilotos_df.columns:
        mapa_eq = dict(zip(pilotos_df['nome'].astype(str), pilotos_df['equipe'].astype(str)))
        equipes = [mapa_eq.get(str(p), '') for p in pilotos_sel]
        equipes_validas = [e for e in equipes if e]
        if len(set(equipes_validas)) < len(equipes_validas):
            return False

    return True


def _get_resumo_ultimas_apostas(usuario_id: int, apostas_df: pd.DataFrame, provas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if apostas_df.empty:
        return []
    ap = apostas_df[apostas_df['usuario_id'] == usuario_id].copy()
    if ap.empty:
        return []
    if 'data_envio' in ap.columns:
        ap['__envio'] = pd.to_datetime(ap['data_envio'], errors='coerce')
        ap = ap.sort_values('__envio')
    ap = ap.drop_duplicates(subset=['prova_id'], keep='last')
    ap = ap.sort_values('prova_id', ascending=False).head(limite)

    provas_nome = {}
    if not provas_df.empty and 'id' in provas_df.columns and 'nome' in provas_df.columns:
        provas_nome = dict(zip(provas_df['id'], provas_df['nome']))

    out = []
    for _, row in ap.iterrows():
        try:
            fichas = [int(x) for x in str(row.get('fichas', '')).split(',') if str(x).strip() != '']
        except Exception:
            fichas = []
        out.append({
            'prova': str(provas_nome.get(row.get('prova_id'), row.get('nome_prova', ''))),
            'pilotos': [p.strip() for p in str(row.get('pilotos', '')).split(',') if p.strip()],
            'fichas': fichas,
            'piloto_11': str(row.get('piloto_11', '')).strip()
        })
    return out


def _get_resumo_cenario_campeonato(resultados_df: pd.DataFrame, provas_df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if resultados_df.empty:
        return []
    res = resultados_df.copy()
    if 'prova_id' in res.columns:
        res = res.sort_values('prova_id', ascending=False).head(limite)

    provas_nome = {}
    if not provas_df.empty and 'id' in provas_df.columns and 'nome' in provas_df.columns:
        provas_nome = dict(zip(provas_df['id'], provas_df['nome']))

    out = []
    for _, row in res.iterrows():
        posicoes = {}
        try:
            posicoes = ast.literal_eval(str(row.get('posicoes', '{}')))
            if not isinstance(posicoes, dict):
                posicoes = {}
        except Exception:
            posicoes = {}
        top3 = [str(posicoes.get(i, '')).strip() for i in [1, 2, 3]]
        out.append({
            'prova': str(provas_nome.get(row.get('prova_id'), f"Prova {row.get('prova_id')}")),
            'top3': [p for p in top3 if p]
        })
    return out


def _gerar_aposta_perplexity(pilotos_df: pd.DataFrame, regras: dict, nome_prova: str, tipo_prova: str, ultimas_apostas: list[dict], cenario: list[dict]) -> tuple[list[str], list[int], str] | None:
    api_key = ""
    model = "sonar"
    try:
        api_key = st.secrets.get("PERPLEXITY_API_KEY", "")
        model = st.secrets.get("PERPLEXITY_MODEL", "sonar")
    except Exception:
        api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        model = os.environ.get("PERPLEXITY_MODEL", "sonar")
    if not api_key:
        return None

    pilotos_disponiveis = pilotos_df['nome'].astype(str).tolist() if not pilotos_df.empty else []
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

    system_prompt = (
        "Você é um assistente de estratégia de bolão de F1. "
        "Responda apenas JSON válido, sem markdown. "
        "Não invente pilotos fora da lista disponível. "
        "Se houver incerteza, faça uma aposta conservadora e viável."
    )
    user_prompt = (
        f"Prova alvo: {nome_prova} ({tipo_prova}).\n"
        f"Pilotos disponíveis: {pilotos_disponiveis}\n"
        f"Regras: min_pilotos={min_pilotos}, quantidade_fichas={qtd_fichas}, fichas_por_piloto={fichas_max}, mesma_equipe={permite_mesma_equipe}.\n"
        f"Últimas 3 apostas do participante: {ultimas_apostas}\n"
        f"Cenário recente do campeonato (últimas provas): {cenario}\n"
        "Gere uma aposta viável com este formato JSON EXATO: "
        "{\"pilotos\": [\"Nome\"], \"fichas\": [1,2], \"piloto_11\": \"Nome\"}."
    )

    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 260,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extrair_json_texto(content)
        if not parsed:
            return None
        pilotos = [str(p).strip() for p in parsed.get('pilotos', []) if str(p).strip()]
        fichas = [int(x) for x in parsed.get('fichas', [])]
        piloto_11 = str(parsed.get('piloto_11', '')).strip()
        if not pilotos or not fichas or not piloto_11:
            return None
        return pilotos, fichas, piloto_11
    except Exception as e:
        logger.warning(f"Falha na geração via Perplexity para aposta estratégica: {e}")
        return None

def _parse_datetime_sp(date_str: str, time_str: str):
    """Tenta parsear data e hora com ou sem segundos e retorna timezone America/Sao_Paulo."""
    return parse_datetime_sao_paulo(date_str, time_str)

def pode_fazer_aposta(data_prova_str, horario_prova_str, horario_usuario=None):
    """
    Verifica se o usuário pode fazer aposta comparando horário local com horário de São Paulo.
    """
    try:
        horario_limite_sp = _parse_datetime_sp(data_prova_str, horario_prova_str)

        if horario_usuario is None:
            horario_usuario = now_sao_paulo()
        elif not horario_usuario.tzinfo:
            horario_usuario = horario_usuario.replace(tzinfo=SAO_PAULO_TZ)

        horario_usuario_utc = horario_usuario.astimezone(ZoneInfo("UTC"))
        horario_limite_utc = horario_limite_sp.astimezone(ZoneInfo("UTC"))

        pode = horario_usuario_utc <= horario_limite_utc
        mensagem = f"Aposta {'permitida' if pode else 'bloqueada'} (Horário limite SP: {horario_limite_sp.strftime('%d/%m/%Y %H:%M:%S')})"

        return pode, mensagem, horario_limite_sp
    except Exception as e:
        return False, f"Erro ao validar horário: {str(e)}", None

def salvar_aposta(
    usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova,
    automatica=0, horario_forcado=None, temporada: str | None = None, show_errors=True,
    permitir_salvar_tardia: bool = False
):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        if show_errors:
            st.error(f"IDs inválidos: usuario_id={usuario_id}, prova_id={prova_id} ({e})")
        return False

    nome_prova_bd, data_prova, horario_prova = get_horario_prova(prova_id)
    if not horario_prova or not nome_prova_bd or not data_prova:
        if show_errors:
            st.error("Prova não encontrada ou horário/nome/data não cadastrados.")
        return False

    # Determinar tipo da prova usando coluna `tipo` quando disponível; fallback por nome
    try:
        prov_df = get_provas_df(temporada)
        tipo_col = None
        if not prov_df.empty:
            row = prov_df[prov_df['id'] == prova_id]
            if not row.empty and 'tipo' in row.columns and pd.notna(row.iloc[0]['tipo']):
                tipo_col = str(row.iloc[0]['tipo']).strip()
        tipo_prova_regra = 'Sprint' if (tipo_col and tipo_col.lower() == 'sprint') or ('sprint' in str(nome_prova_bd).lower()) else 'Normal'
    except Exception:
        tipo_prova_regra = 'Sprint' if 'sprint' in str(nome_prova_bd).lower() else 'Normal'
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova_regra)
    
    quantidade_fichas = regras.get('quantidade_fichas', 15)
    min_pilotos = regras.get('min_pilotos', 3)
    max_por_piloto = int(regras.get('fichas_por_piloto', quantidade_fichas))

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < min_pilotos or sum(fichas) != quantidade_fichas or (fichas and max(fichas) > max_por_piloto):
        if show_errors:
            msg = f"Regra exige: mín {min_pilotos} pilotos, total {quantidade_fichas} fichas, máx {max_por_piloto} por piloto."
            st.error(f"Dados inválidos para aposta. {msg}")
        return False

    horario_limite = _parse_datetime_sp(data_prova, horario_prova)

    agora_sp = horario_forcado or now_sao_paulo()
    tipo_aposta = 0 if agora_sp <= horario_limite else 1

    dados_pilotos = ', '.join(pilotos)
    dados_fichas = ', '.join(map(str, fichas))

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        if show_errors:
            st.error(f"Usuário não encontrado: id={usuario_id}")
        return False
    status_usuario = str(usuario.get('status', '')).strip().lower()
    if status_usuario and status_usuario != 'ativo':
        if show_errors:
            st.error("Usuário inativo não pode efetuar apostas.")
        return False

    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info('apostas')")
            aposta_cols = [r[1] for r in c.fetchall()]

            if temporada is None:
                temporada = str(datetime.now().year)

            if 'temporada' in aposta_cols:
                c.execute('DELETE FROM apostas WHERE usuario_id=? AND prova_id=? AND temporada=?', (usuario_id, prova_id, temporada))
            else:
                c.execute('DELETE FROM apostas WHERE usuario_id=? AND prova_id=?', (usuario_id, prova_id))

            if tipo_aposta == 0 or permitir_salvar_tardia:
                data_envio = agora_sp.isoformat()
                if 'temporada' in aposta_cols:
                    c.execute(
                        '''
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica, temporada)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            usuario_id, prova_id, data_envio, ','.join(pilotos), ','.join(map(str, fichas)),
                            piloto_11, nome_prova_bd, automatica, temporada
                        )
                    )
                else:
                    c.execute(
                        '''
                        INSERT INTO apostas
                        (usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, nome_prova, automatica)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            usuario_id, prova_id, data_envio, ','.join(pilotos), ','.join(map(str, fichas)),
                            piloto_11, nome_prova_bd, automatica
                        )
                    )
            else:
                # Aposta tardia não salva quando não permitido
                if show_errors:
                    st.error("Aposta fora do horário limite.")
                try:
                    tentativa_str = agora_sp.strftime('%d/%m/%Y %H:%M:%S')
                    limite_str = horario_limite.strftime('%d/%m/%Y %H:%M:%S')
                    corpo_email = (
                        f"<p>Olá {html.escape(usuario['nome'])},</p>"
                        f"<p>Sua aposta para a prova <b>{html.escape(nome_prova_bd)}</b> não foi efetivada.</p>"
                        "<p><b>Motivo:</b> prazo encerrado (aposta fora do horário limite).</p>"
                        f"<p><b>Horário limite:</b> {limite_str} (America/Sao_Paulo)</p>"
                        f"<p><b>Horário da tentativa:</b> {tentativa_str} (America/Sao_Paulo)</p>"
                        "<p>Se precisar de ajuda, fale com a administração.</p>"
                    )
                    enviar_email(usuario['email'], f"Aposta não efetivada - {nome_prova_bd}", corpo_email)
                except Exception as e:
                    logger.warning(f"Falha ao enviar email de aposta rejeitada para {usuario.get('email')}: {e}")
                try:
                    registrar_log_aposta(
                        usuario_id=usuario_id,
                        prova_id=prova_id,
                        apostador=usuario['nome'],
                        pilotos=dados_pilotos,
                        aposta=dados_fichas,
                        nome_prova=nome_prova_bd,
                        piloto_11=piloto_11,
                        tipo_aposta=tipo_aposta,
                        automatica=automatica,
                        horario=agora_sp,
                        temporada=temporada,
                        status='Rejeitada'
                    )
                except Exception as e:
                    logger.warning(f"Falha ao registrar log de aposta rejeitada para {usuario.get('email')}: {e}")
                return False
            conn.commit()

            try:
                analise = gerar_analise_aposta_com_probabilidade(
                    nome_usuario=usuario.get('nome', ''),
                    contexto_aposta=f"Prova {nome_prova_bd}",
                    detalhes_aposta=(
                        f"Pilotos: {', '.join(pilotos)}; "
                        f"Fichas: {', '.join(map(str, fichas))}; "
                        f"11º: {piloto_11}"
                    ),
                )
                comentario = str(analise.get("comentario", "")).strip()
                probabilidade = analise.get("probabilidade")
                resumo = str(analise.get("resumo", "")).strip()

                previsao_html = ""
                if comentario:
                    previsao_html += "<p><b>Comentário sarcástico:</b><br>" + "<br>".join(html.escape(comentario).splitlines()) + "</p>"
                if probabilidade is not None:
                    previsao_html += f"<p><b>Probabilidade estimada de acerto:</b> {int(probabilidade)}%</p>"
                if resumo:
                    previsao_html += "<p><b>Base da estimativa:</b> " + html.escape(resumo) + "</p>"

                corpo_email = (
                    f"<p>Olá {html.escape(usuario['nome'])},</p>"
                    f"<p>Sua aposta para a prova <b>{html.escape(nome_prova_bd)}</b> foi registrada com sucesso.</p>"
                    "<p><b>Detalhes:</b></p>"
                    "<ul>"
                    f"<li>Pilotos: {html.escape(', '.join(pilotos))}</li>"
                    f"<li>Fichas: {html.escape(', '.join(map(str, fichas)))}</li>"
                    f"<li>Palpite para 11º colocado: {html.escape(piloto_11)}</li>"
                    "</ul>"
                    f"{previsao_html}"
                    "<p><small><b>Aviso de estimativa:</b> a probabilidade informada é apenas uma projeção estatística/opinativa com base em informações disponíveis e pode variar a qualquer momento. Não constitui garantia de resultado esportivo nem direito a pontuação, prevalecendo sempre as regras oficiais do bolão.</small></p>"
                    "<p>Boa sorte!</p>"
                )
                enviar_email(usuario['email'], f"Aposta registrada - {nome_prova_bd}", corpo_email)
            except Exception as e:
                logger.warning(f"Falha ao enviar email de aposta para {usuario.get('email')}: {e}")

    except Exception as e:
        if show_errors:
            st.error(f"Erro ao salvar aposta: {str(e)}")
        return False

    registrar_log_aposta(
        usuario_id=usuario_id,
        prova_id=prova_id,
        apostador=usuario['nome'],
        pilotos=dados_pilotos,
        aposta=dados_fichas,
        nome_prova=nome_prova_bd,
        piloto_11=piloto_11,
        tipo_aposta=tipo_aposta,
        automatica=automatica,
        horario=agora_sp,
        temporada=temporada,
        status='Registrada'
    )
    return True

def gerar_aposta_aleatoria(pilotos_df):
    import random
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = pilotos_df[pilotos_df['status'] == 'Ativo']
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    if len(equipes_unicas) < 3 or pilotos_df.empty:
        return [], [], None
    
    equipes_selecionadas = random.sample(equipes_unicas, min(5, len(equipes_unicas)))
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
        if pilotos_equipe:
            pilotos_sel.append(random.choice(pilotos_equipe))
    
    # Validar se conseguimos selecionar piloto suficientes
    if len(pilotos_sel) < 3:
        return [], [], None
    
    # Gerar fichas que totalizam exatamente 15
    num_pilotos = len(pilotos_sel)
    fichas = [1] * num_pilotos  # Cada piloto começa com 1 ficha
    fichas_restantes = 15 - num_pilotos  # Fichas a distribuir
    
    # Distribuir fichas restantes aleatoriamente
    for _ in range(fichas_restantes):
        idx = random.randint(0, num_pilotos - 1)
        fichas[idx] += 1
        
    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)
    
    return pilotos_sel, fichas, piloto_11

def gerar_aposta_aleatoria_com_regras(pilotos_df, regras: dict):
    """Gera aposta aleatória respeitando as regras (total de fichas, mínimo de pilotos, limite por piloto).
    Considera possibilidade de mesma equipe quando necessário para atingir o número de pilotos requerido.
    """
    import random
    import math
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = pilotos_df[pilotos_df['status'] == 'Ativo']
    if pilotos_df.empty:
        return [], [], None
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))

    # Quantidade mínima de pilotos para suportar o limite por piloto
    pilotos_necessarios_por_cap = max(1, math.ceil(qtd_fichas / max(1, fichas_max)))
    alvo_pilotos = max(min_pilotos, pilotos_necessarios_por_cap)

    pilotos_sel = []
    if len(equipes_unicas) >= alvo_pilotos:
        # Escolhe equipes diferentes
        equipes_selecionadas = random.sample(equipes_unicas, alvo_pilotos)
        for equipe in equipes_selecionadas:
            pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
    else:
        # Não há equipes suficientes; se permitido, escolhe pilotos adicionais de equipes repetidas
        if not permite_mesma_equipe:
            return [], [], None
        # Primeiro pega um de cada equipe
        for equipe in equipes_unicas:
            pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
            if pilotos_equipe:
                pilotos_sel.append(random.choice(pilotos_equipe))
        # Completa com pilotos aleatórios (permitindo 2 da mesma equipe)
        todos_pilotos = pilotos_df['nome'].tolist()
        safety = 10000
        while len(pilotos_sel) < alvo_pilotos and safety > 0:
            safety -= 1
            candidato = random.choice(todos_pilotos)
            if candidato not in pilotos_sel:
                pilotos_sel.append(candidato)
        if len(pilotos_sel) < alvo_pilotos:
            return [], [], None

    # Distribuição de fichas obedecendo limite por piloto
    num_pilotos = len(pilotos_sel)
    fichas = [1] * num_pilotos
    fichas_restantes = qtd_fichas - num_pilotos
    if fichas_restantes < 0:
        return [], [], None
    safety = 10000
    while fichas_restantes > 0 and safety > 0:
        safety -= 1
        idx = random.randint(0, num_pilotos - 1)
        if fichas[idx] < fichas_max:
            fichas[idx] += 1
            fichas_restantes -= 1
    if fichas_restantes > 0:
        return [], [], None

    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)

    return pilotos_sel, fichas, piloto_11

def ajustar_aposta_para_regras(pilotos: list[str], fichas: list[int], regras: dict, pilotos_df: pd.DataFrame):
    """Ajusta uma aposta existente (copiada) para obedecer regras da temporada.
    - Garante soma de fichas conforme regra
    - Respeita limite por piloto
    - Garante mínimo de pilotos (adicionando pilotos se necessário)
    Retorna (pilotos_ajustados, fichas_ajustadas) ou ([], []) se não for possível.
    """
    import math, random
    if not pilotos:
        return [], []
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))

    # Normalizar tamanhos
    n = min(len(pilotos), len(fichas))
    pilotos = [p.strip() for p in pilotos[:n]]
    fichas = [int(x) for x in fichas[:n]]
    # Trocar zeros negativos por zero e tratar negativos
    fichas = [max(0, x) for x in fichas]

    # Garante mínimo de pilotos
    if len(pilotos) < min_pilotos:
        todos_pilotos = pilotos_df['nome'].tolist()
        candidatos = [p for p in todos_pilotos if p not in set(pilotos)]
        safety = 10000
        while len(pilotos) < min_pilotos and candidatos and safety > 0:
            safety -= 1
            novo = random.choice(candidatos)
            candidatos.remove(novo)
            pilotos.append(novo)
            fichas.append(0)
        if len(pilotos) < min_pilotos:
            return [], []

    # Impõe limite por piloto
    fichas = [min(x, fichas_max) for x in fichas]

    soma = sum(fichas)
    # Ajusta soma para o exigido
    if soma > qtd_fichas:
        # Reduz das maiores entradas primeiro
        for _ in range(soma - qtd_fichas):
            idx_max = max(range(len(fichas)), key=lambda i: fichas[i])
            if fichas[idx_max] > 0:
                fichas[idx_max] -= 1
    elif soma < qtd_fichas:
        # Aumenta respeitando limite por piloto
        faltam = qtd_fichas - soma
        safety = 100000
        while faltam > 0 and safety > 0:
            safety -= 1
            idx = random.randint(0, len(fichas) - 1)
            if fichas[idx] < fichas_max:
                fichas[idx] += 1
                faltam -= 1
            # Se ficar travado por limite, tenta expandir pilotos
            if safety % 1000 == 0 and faltam > 0:
                todos_pilotos = pilotos_df['nome'].tolist()
                candidatos = [p for p in todos_pilotos if p not in set(pilotos)]
                if candidatos:
                    novo = random.choice(candidatos)
                    pilotos.append(novo)
                    fichas.append(0)
    # Validação final
    if sum(fichas) != qtd_fichas or len(pilotos) < min_pilotos:
        return [], []
    return pilotos, fichas

def _determinar_tipo_prova(prova_row: pd.Series | dict, nome_prova: str | None) -> str:
    try:
        if isinstance(prova_row, dict):
            t = prova_row.get('tipo')
        else:
            t = prova_row['tipo'] if 'tipo' in prova_row and pd.notna(prova_row['tipo']) else None
    except Exception:
        t = None
    if t and str(t).strip().lower() == 'sprint':
        return 'Sprint'
    if nome_prova and 'sprint' in str(nome_prova).lower():
        return 'Sprint'
    return 'Normal'

def gerar_aposta_automatica(usuario_id, prova_id, nome_prova, apostas_df, provas_df, temporada=None):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"
        
    prova_atual = provas_df[provas_df['id'] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."
        
    data_prova = prova_atual['data'].iloc[0]
    horario_prova = prova_atual['horario_prova'].iloc[0]
    horario_limite = _parse_datetime_sp(data_prova, horario_prova)
    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)
    
    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id) & 
        (apostas_df["prova_id"] == prova_id) & 
        ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."
        
    ap_ant = pd.DataFrame()
    prova_id_min = None
    try:
        prova_id_min = int(provas_df['id'].min()) if not provas_df.empty else None
    except Exception:
        prova_id_min = None

    # Encontrar a prova anterior pela data/horario (na mesma temporada)
    try:
        provas_tmp = provas_df.copy()
        if 'data' in provas_tmp.columns:
            provas_tmp['__data_dt'] = pd.to_datetime(provas_tmp['data'], errors='coerce')
        else:
            provas_tmp['__data_dt'] = pd.NaT
        provas_tmp['__hora_str'] = provas_tmp.get('horario_prova', '00:00:00')
        provas_tmp['__hora_dt'] = pd.to_datetime(provas_tmp['__hora_str'], format='%H:%M:%S', errors='coerce')
        provas_tmp['__hora_dt'] = provas_tmp['__hora_dt'].fillna(
            pd.to_datetime('00:00:00', format='%H:%M:%S')
        )
        provas_tmp['__prova_dt'] = provas_tmp['__data_dt'] + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.hour, unit='h'
        ) + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.minute, unit='m'
        ) + pd.to_timedelta(
            provas_tmp['__hora_dt'].dt.second, unit='s'
        )
        provas_tmp = provas_tmp.sort_values(['__prova_dt', 'id'])

        prova_atual_row = provas_tmp[provas_tmp['id'] == prova_id]
        if not prova_atual_row.empty:
            prova_atual_dt = prova_atual_row.iloc[0]['__prova_dt']
            provas_anteriores = provas_tmp[provas_tmp['__prova_dt'] < prova_atual_dt]
            if not provas_anteriores.empty:
                prova_ant_id = int(provas_anteriores.iloc[-1]['id'])
                ap_ant = apostas_df[
                    (apostas_df['usuario_id'] == usuario_id) &
                    (apostas_df['prova_id'] == prova_ant_id)
                ]
    except Exception:
        ap_ant = pd.DataFrame()

    if ap_ant.empty:
        try:
            provas_sorted = provas_df.sort_values('id')
            prev_rows = provas_sorted[provas_sorted['id'] < prova_id]
            if not prev_rows.empty:
                prova_ant_id = int(prev_rows.iloc[-1]['id'])
                ap_ant = apostas_df[
                    (apostas_df['usuario_id'] == usuario_id) &
                    (apostas_df['prova_id'] == prova_ant_id)
                ]
        except Exception:
            ap_ant = pd.DataFrame()
    
    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = pilotos_df[pilotos_df['status'] == 'Ativo']

    if not ap_ant.empty:
        ap_ant = ap_ant.iloc[0]
        pilotos_ant = [p.strip() for p in ap_ant['pilotos'].split(",")]
        fichas_ant = list(map(int, ap_ant['fichas'].split(",")))
        piloto_11_ant = ap_ant['piloto_11'].strip()
        # Ajustar aposta copiada para obedecer regras da prova atual (ex.: Sprint x Normal)
        pilotos_aj, fichas_aj = ajustar_aposta_para_regras(pilotos_ant, fichas_ant, regras, pilotos_df)
        if not pilotos_aj:
            # Se não conseguir ajustar, gera aleatória com regras
            pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        else:
            pilotos_ant, fichas_ant = pilotos_aj, fichas_aj
    else:
        # Gerar aleatoria apenas na primeira prova do campeonato
        if prova_id_min is not None and prova_id != prova_id_min:
            return False, "Sem aposta anterior para copiar. Gere apenas na primeira prova."
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        
    if not pilotos_ant:
        return False, "Não há dados válidos para gerar aposta automática."
        
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(automatica) FROM apostas WHERE usuario_id=?', (usuario_id,))
        max_auto = c.fetchone()[0] or 0
        nova_auto = 1 if max_auto is None else max_auto + 1
        
    sucesso = salvar_aposta(
        usuario_id, prova_id, pilotos_ant, fichas_ant, piloto_11_ant, nome_prova,
        automatica=nova_auto, horario_forcado=horario_limite, temporada=temporada, show_errors=False,
        permitir_salvar_tardia=True
    )
    
    return (True, "Aposta automática gerada!") if sucesso else (False, "Falha ao salvar.")


def gerar_aposta_sem_ideias(usuario_id, prova_id, nome_prova, temporada=None):
    """Gera e efetiva aposta para o participante dentro do prazo, com tentativa estratégica via Perplexity e fallback aleatório seguro."""
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: {e}"

    provas_df = get_provas_df(temporada)
    prova_atual = provas_df[provas_df['id'] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."

    data_prova = str(prova_atual['data'].iloc[0])
    horario_prova = str(prova_atual['horario_prova'].iloc[0])
    pode, msg, _ = pode_fazer_aposta(data_prova, horario_prova)
    if not pode:
        return False, f"Aposta fora do prazo. {msg}"

    tipo_prova = _determinar_tipo_prova(prova_atual.iloc[0], nome_prova)
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova)

    pilotos_df = get_pilotos_df()
    if not pilotos_df.empty and 'status' in pilotos_df.columns:
        pilotos_df = pilotos_df[pilotos_df['status'] == 'Ativo']
    if pilotos_df.empty:
        return False, "Não há pilotos ativos para gerar aposta."

    apostas_df = get_apostas_df(temporada)
    resultados_df = get_resultados_df(temporada)
    ultimas_apostas = _get_resumo_ultimas_apostas(usuario_id, apostas_df, provas_df, limite=3)
    cenario = _get_resumo_cenario_campeonato(resultados_df, provas_df, limite=3)

    origem = "aleatória"
    sugestao = _gerar_aposta_perplexity(pilotos_df, regras, nome_prova, tipo_prova, ultimas_apostas, cenario)
    if sugestao:
        pilotos_sel, fichas_sel, piloto_11_sel = sugestao
        if _aposta_valida_regras(pilotos_sel, fichas_sel, piloto_11_sel, pilotos_df, regras):
            origem = "estratégica"
        else:
            sugestao = None

    if not sugestao:
        pilotos_sel, fichas_sel, piloto_11_sel = gerar_aposta_aleatoria_com_regras(pilotos_df, regras)
        if not pilotos_sel:
            return False, "Não foi possível gerar aposta viável com as regras atuais."

    ok = salvar_aposta(
        usuario_id=usuario_id,
        prova_id=prova_id,
        pilotos=pilotos_sel,
        fichas=fichas_sel,
        piloto_11=piloto_11_sel,
        nome_prova=nome_prova,
        automatica=0,
        temporada=temporada,
        show_errors=False,
        permitir_salvar_tardia=False,
    )

    if not ok:
        return False, "Falha ao salvar aposta gerada."

    if origem == "estratégica":
        return True, "Aposta 'Sem ideias' gerada com estratégia assistida e registrada!"
    return True, "Aposta 'Sem ideias' aleatória (fallback) registrada com sucesso!"

def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação usando:
    - Tabelas de pontos da REGRA (Normal/Sprint), com fallback FIA hardcoded
    - Fichas DINÂMICAS da aposta do usuário
    - Bônus 11º DINÂMICO da regra da temporada
    - Penalidades DINÂMICAS das regras
    
    Fórmula: Pontos = (Pontos_Regra x Fichas) + Bônus_11º - Penalidades
    """
    import ast
    
    # Tabelas de pontos FIXAS da FIA
    PONTOS_F1_NORMAL = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    PONTOS_SPRINT = [8, 7, 6, 5, 4, 3, 2, 1]
    
    ress_map = {}
    abandonos_map = {}
    for _, r in res_df.iterrows():
        try:
            ress_map[r['prova_id']] = ast.literal_eval(r['posicoes'])
        except Exception:
            continue
        # Ler lista de abandonos (comma-separated), se disponível
        try:
            if 'abandono_pilotos' in res_df.columns:
                raw = r.get('abandono_pilotos', '')
                if raw is None:
                    raw = ''
                # Normaliza string -> lista de nomes limpos
                aband_list = [p.strip() for p in str(raw).split(',') if p and p.strip()]
                abandonos_map[r['prova_id']] = set(aband_list)
            else:
                abandonos_map[r['prova_id']] = set()
        except Exception:
            abandonos_map[r['prova_id']] = set()
    
    # Mapear tipo de prova com fallback pelo nome (contém "Sprint")
    tipos = []
    if 'tipo' in prov_df.columns:
        tipos = prov_df['tipo'].fillna('').astype(str).tolist()
    else:
        tipos = [''] * len(prov_df)
    nomes = prov_df['nome'].fillna('').astype(str).tolist() if 'nome' in prov_df.columns else [''] * len(prov_df)
    tipos_resolvidos = []
    for i in range(len(prov_df)):
        t = tipos[i].strip().lower()
        n = nomes[i].strip().lower()
        if t == 'sprint' or ('sprint' in n):
            tipos_resolvidos.append('Sprint')
        else:
            tipos_resolvidos.append('Normal')
    tipos_prova = dict(zip(prov_df['id'], tipos_resolvidos))
    temporadas_prova = dict(zip(prov_df['id'], prov_df['temporada'] if 'temporada' in prov_df.columns else [str(datetime.now().year)]*len(prov_df)))
    has_temp_aposta = 'temporada' in ap_df.columns
    
    pontos = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta['prova_id']
        
        if prova_id not in ress_map:
            pontos.append(None)
            continue
        
        res = ress_map[prova_id]
        tipo = tipos_prova.get(prova_id, 'Normal')
        temporada_aposta = None
        if has_temp_aposta:
            try:
                temporada_aposta = aposta.get('temporada', None)
            except Exception:
                temporada_aposta = None
        if temporada_aposta is not None and str(temporada_aposta).strip() != "" and not pd.isna(temporada_aposta):
            temporada_prova = str(temporada_aposta)
        else:
            temporada_prova = temporadas_prova.get(prova_id, str(datetime.now().year))
        
        # Busca REGRAS DINÂMICAS da temporada (não altera pontos FIA)
        regras = get_regras_aplicaveis(temporada_prova, tipo)
        
        # Seleciona tabela de pontos da REGRA.
        # Corridas Sprint sempre usam a tabela de sprint; regra_sprint só afeta fichas/minimo, não a tabela.
        if tipo == 'Sprint':
            pontos_tabela = regras.get('pontos_sprint_posicoes') or regras.get('pontos_posicoes') or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_SPRINT
        else:
            pontos_tabela = regras.get('pontos_posicoes') or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_F1_NORMAL
        n_posicoes = len(pontos_tabela)
        
        # Bônus 11º DINÂMICO da regra
        bonus_11 = regras.get('pontos_11_colocado', 25)
        
        # Dados da aposta (fichas são DINÂMICAS - definidas pelo usuário)
        pilotos = [p.strip() for p in aposta['pilotos'].split(",")]
        fichas = list(map(int, aposta['fichas'].split(",")))  # DINÂMICO
        piloto_11 = aposta['piloto_11']
        automatica = int(aposta.get('automatica', 0))
        
        piloto_para_pos = {str(v).strip(): int(k) for k, v in res.items()}
        
        # Cálculo base: Pontos da Regra x Fichas (dinâmico)
        # Observação: multiplicador de sprint será aplicado APÓS bônus e penalidades
        pt = 0
        for i in range(len(pilotos)):
            piloto = pilotos[i]
            ficha = fichas[i] if i < len(fichas) else 0
            pos_real = piloto_para_pos.get(piloto, None)
            
            if pos_real is not None and 1 <= pos_real <= n_posicoes:
                base = pontos_tabela[pos_real - 1]
                pt += ficha * base
        
        # Bônus 11º colocado (DINÂMICO da regra)
        piloto_11_real = res.get(11, "")
        if piloto_11 == piloto_11_real:
            pt += bonus_11
        
        # Penalidade por abandono (DINÂMICA da regra):
        # Deduz `pontos_penalidade` por cada piloto apostado que esteja na lista de abandonos
        if regras.get('penalidade_abandono'):
            aband_prova = abandonos_map.get(prova_id, set())
            if aband_prova:
                # Conta apenas abandonos dentre os pilotos apostados (exclui palpite do 11º)
                num_aband_apostados = sum(1 for p in pilotos if p in aband_prova)
                deduz = regras.get('pontos_penalidade', 0) * num_aband_apostados
                if deduz:
                    pt -= deduz

        # Aplicar multiplicador de sprint APÓS bônus e penalidades
        if tipo == 'Sprint' and regras.get('pontos_dobrada'):
            pt = pt * 2

        # Penalidade apostas automáticas consecutivas (DINÂMICA)
        if automatica >= 2:
            penalidade_auto_percent = regras.get('penalidade_auto_percent', 20)
            fator = max(0, 1 - (float(penalidade_auto_percent) / 100))
            pt = round(pt * fator, 2)
        
        pontos.append(pt)
    
    return pontos

def salvar_classificacao_prova(p_id, df_c, temp=None):
    if temp is None:
        temp = str(datetime.now().year)
    
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info('posicoes_participantes')")
        cols = [r[1] for r in c.fetchall()]
        has_temporada = 'temporada' in cols
        
        # Safeguard: limpar entradas existentes para esta prova e temporada
        if has_temporada:
            c.execute('DELETE FROM posicoes_participantes WHERE prova_id=? AND temporada=?', (p_id, temp))
        else:
            c.execute('DELETE FROM posicoes_participantes WHERE prova_id=?', (p_id,))
        
        for _, r in df_c.iterrows():
            if has_temporada:
                c.execute(
                    'INSERT OR REPLACE INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos, temporada) VALUES (?,?,?,?,?)',
                    (p_id, int(r['usuario_id']), int(r['posicao']), float(r['pontos']), temp)
                )
            else:
                c.execute(
                    'INSERT OR REPLACE INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos) VALUES (?,?,?,?)',
                    (p_id, int(r['usuario_id']), int(r['posicao']), float(r['pontos']))
                )
        conn.commit()

def atualizar_classificacoes_todas_as_provas(temporada: str | None = None):
    with db_connect() as conn:
        usrs = pd.read_sql('SELECT id FROM usuarios WHERE status = "Ativo"', conn)
        provs = pd.read_sql('SELECT id, nome, data, tipo, temporada FROM provas', conn)
        apts = pd.read_sql('SELECT usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, automatica, temporada FROM apostas', conn)
        ress = pd.read_sql('SELECT prova_id, posicoes, abandono_pilotos FROM resultados', conn)
        
        import ast
        # Se temporada for fornecida, processa apenas provas dessa temporada
        if temporada and 'temporada' in provs.columns:
            provs = provs[provs['temporada'] == temporada]

        # Identificar primeira prova por temporada (quando disponível)
        primeira_prova_por_temp = {}
        if not provs.empty:
            if 'temporada' in provs.columns and 'data' in provs.columns:
                provs_dt = provs.copy()
                provs_dt['__data_dt'] = pd.to_datetime(provs_dt['data'], errors='coerce')
                for temp_val, grp in provs_dt.groupby('temporada'):
                    grp = grp.sort_values('__data_dt')
                    if not grp.empty:
                        primeira_prova_por_temp[str(temp_val)] = int(grp.iloc[0]['id'])
            elif 'data' in provs.columns:
                provs_dt = provs.copy()
                provs_dt['__data_dt'] = pd.to_datetime(provs_dt['data'], errors='coerce')
                provs_dt = provs_dt.sort_values('__data_dt')
                if not provs_dt.empty:
                    primeira_prova_por_temp[str(datetime.now().year)] = int(provs_dt.iloc[0]['id'])
            elif not provs.empty:
                primeira_prova_por_temp[str(datetime.now().year)] = int(provs.iloc[0]['id'])
        
        for _, pr in provs.iterrows():
            pid = pr['id']
            if pid not in ress['prova_id'].values:
                continue
            
            temporada_prova = pr.get('temporada', str(datetime.now().year))
            aps = apts[apts['prova_id'] == pid]
            # Filtra apostas pela temporada se a coluna existir
            if 'temporada' in aps.columns:
                aps = aps[(aps['temporada'] == temporada_prova) | (aps['temporada'].isna())]
            if aps.empty:
                continue
                
            res_row = ress[ress['prova_id'] == pid].iloc[0]
            res_p = ast.literal_eval(res_row['posicoes'])
            piloto_11_real = res_p.get(11, "")
            
            tab = []
            first_no_base_flags = {}
            for _, u in usrs.iterrows():
                ap = aps[aps['usuario_id'] == u['id']]
                
                if ap.empty:
                    pontos_val = 0
                    data_envio = None
                    acerto_11 = 0
                    # Primeira prova sem base
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        first_no_base_flags[int(u['id'])] = True
                else:
                    p_list = calcular_pontuacao_lote(ap, ress, provs)
                    pontos_val = sum(p_list) if p_list else 0
                    data_envio = ap.iloc[0].get('data_envio', None)
                    acerto_11 = 1 if ap.iloc[0]['piloto_11'] == piloto_11_real else 0
                    # Primeira prova com aposta automática (sem base)
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        try:
                            if int(ap.iloc[0].get('automatica', 0)) > 0:
                                first_no_base_flags[int(u['id'])] = True
                        except Exception:
                            pass
                
                tab.append({
                    'usuario_id': u['id'],
                    'pontos': pontos_val,
                    'data_envio': data_envio,
                    'acerto_11': acerto_11
                })

            # Aplicar regra de 85% do pior pontuador na primeira corrida sem base
            if first_no_base_flags:
                try:
                    pontos_validos = [
                        t['pontos'] for t in tab
                        if t['pontos'] is not None and not first_no_base_flags.get(int(t['usuario_id']), False)
                    ]
                    pior_pontuador = min(pontos_validos) if pontos_validos else 0
                except Exception:
                    pior_pontuador = 0
                for t in tab:
                    if first_no_base_flags.get(int(t['usuario_id']), False):
                        t['pontos'] = round(pior_pontuador * 0.85, 2)
            
            df = pd.DataFrame(tab)
            df['data_envio'] = pd.to_datetime(df['data_envio'], errors='coerce')
            df = df.sort_values(
                by=['pontos', 'acerto_11', 'data_envio'],
                ascending=[False, False, True]
            ).reset_index(drop=True)
            df['posicao'] = df.index + 1
            salvar_classificacao_prova(pid, df, temporada_prova)
