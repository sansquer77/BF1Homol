import pandas as pd
import streamlit as st
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
from services.email_service import enviar_email
from services.rules_service import get_regras_aplicaveis

def _parse_datetime_sp(date_str: str, time_str: str):
    """Tenta parsear data e hora com ou sem segundos e retorna timezone America/Sao_Paulo."""
    fmts = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
    for fmt in fmts:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", fmt)
            return dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        except ValueError:
            continue
    # Se todas falharem, levanta erro explícito
    raise ValueError(f"Formato de data/hora inválido: '{date_str} {time_str}'")

def pode_fazer_aposta(data_prova_str, horario_prova_str, horario_usuario=None):
    """
    Verifica se o usuário pode fazer aposta comparando horário local com horário de São Paulo.
    """
    try:
        horario_limite_sp = _parse_datetime_sp(data_prova_str, horario_prova_str)

        if horario_usuario is None:
            horario_usuario = datetime.now(ZoneInfo("America/Sao_Paulo"))
        elif not horario_usuario.tzinfo:
            horario_usuario = horario_usuario.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

        horario_usuario_utc = horario_usuario.astimezone(ZoneInfo("UTC"))
        horario_limite_utc = horario_limite_sp.astimezone(ZoneInfo("UTC"))

        pode = horario_usuario_utc <= horario_limite_utc
        mensagem = f"Aposta {'permitida' if pode else 'bloqueada'} (Horário limite SP: {horario_limite_sp.strftime('%d/%m/%Y %H:%M:%S')})"

        return pode, mensagem, horario_limite_sp
    except Exception as e:
        return False, f"Erro ao validar horário: {str(e)}", None

def salvar_aposta(
    usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova,
    automatica=0, horario_forcado=None, temporada: str | None = None, show_errors=True
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

    tipo_prova_regra = "Sprint" if "Sprint" in (nome_prova_bd or "") else "Normal"
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova_regra)
    
    quantidade_fichas = regras.get('quantidade_fichas', 15)
    min_pilotos = regras.get('min_pilotos', 3)

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < min_pilotos or sum(fichas) != quantidade_fichas:
        if show_errors:
            st.error(f"Dados insuficientes para gerar aposta. Regra: {min_pilotos} pilotos e {quantidade_fichas} fichas.")
        return False

    horario_limite = _parse_datetime_sp(data_prova, horario_prova)

    agora_sp = horario_forcado or datetime.now(ZoneInfo("America/Sao_Paulo"))
    tipo_aposta = 0 if agora_sp <= horario_limite else 1

    dados_pilotos = ', '.join(pilotos)
    dados_fichas = ', '.join(map(str, fichas))

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        if show_errors:
            st.error(f"Usuário não encontrado: id={usuario_id}")
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

            if tipo_aposta == 0:
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
            conn.commit()

            try:
                corpo_email = f"""
Olá {usuario['nome']},

Sua aposta para a prova **{nome_prova_bd}** foi registrada com sucesso.

Detalhes:
* Pilotos: {', '.join(pilotos)}
* Fichas: {', '.join(map(str, fichas))}
* Palpite para 11º colocado: {piloto_11}

Boa sorte!
"""
                enviar_email(usuario['email'], f"Aposta registrada - {nome_prova_bd}", corpo_email)
            except:
                pass

    except Exception as e:
        if show_errors:
            st.error(f"Erro ao salvar aposta: {str(e)}")
        return False

    registrar_log_aposta(
        apostador=usuario['nome'],
        pilotos=dados_pilotos,
        aposta=dados_fichas,
        nome_prova=nome_prova_bd,
        piloto_11=piloto_11,
        tipo_aposta=tipo_aposta,
        automatica=automatica,
        horario=agora_sp,
        temporada=temporada
    )
    return True

def gerar_aposta_aleatoria(pilotos_df):
    import random
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
    """Gera aposta aleatória respeitando `quantidade_fichas`, `qtd_minima_pilotos` e `fichas_por_piloto` da regra."""
    import random
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    min_pilotos = int(regras.get('qtd_minima_pilotos') or regras.get('min_pilotos', 3))
    qtd_fichas = int(regras.get('quantidade_fichas', 15))
    fichas_max = int(regras.get('fichas_por_piloto', qtd_fichas))
    if len(equipes_unicas) < min_pilotos or pilotos_df.empty:
        return [], [], None

    equipes_selecionadas = random.sample(equipes_unicas, min(max(min_pilotos, 5), len(equipes_unicas)))
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
        if pilotos_equipe:
            pilotos_sel.append(random.choice(pilotos_equipe))
    
    if len(pilotos_sel) < min_pilotos:
        return [], [], None

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
        else:
            continue
    if fichas_restantes > 0:
        # Não foi possível distribuir devido ao limite por piloto
        return [], [], None

    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)

    return pilotos_sel, fichas, piloto_11

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
    
    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id) & 
        (apostas_df["prova_id"] == prova_id) & 
        ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."
        
    prova_ant_id = prova_id - 1
    ap_ant = apostas_df[(apostas_df['usuario_id'] == usuario_id) & (apostas_df['prova_id'] == prova_ant_id)]
    
    if not ap_ant.empty:
        ap_ant = ap_ant.iloc[0]
        pilotos_ant = [p.strip() for p in ap_ant['pilotos'].split(",")]
        fichas_ant = list(map(int, ap_ant['fichas'].split(",")))
        piloto_11_ant = ap_ant['piloto_11'].strip()
    else:
        # Gerar aposta aleatória respeitando regras da temporada e tipo da prova
        tipo = prova_atual['tipo'].iloc[0] if 'tipo' in prova_atual.columns and pd.notna(prova_atual['tipo'].iloc[0]) else ("Sprint" if "Sprint" in (nome_prova or "") else "Normal")
        regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo)
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria_com_regras(get_pilotos_df(), regras)
        
    if not pilotos_ant:
        return False, "Não há dados válidos para gerar aposta automática."
        
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(automatica) FROM apostas WHERE usuario_id=?', (usuario_id,))
        max_auto = c.fetchone()[0] or 0
        nova_auto = 1 if max_auto is None else max_auto + 1
        
    sucesso = salvar_aposta(
        usuario_id, prova_id, pilotos_ant, fichas_ant, piloto_11_ant, nome_prova,
        automatica=nova_auto, horario_forcado=horario_limite, temporada=temporada, show_errors=False
    )
    
    return (True, "Aposta automática gerada!") if sucesso else (False, "Falha ao salvar.")

def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação usando:
    - Tabelas de pontos FIXAS da FIA (hardcoded)
    - Fichas DINÂMICAS da aposta do usuário
    - Bônus 11º DINÂMICO da regra da temporada
    - Penalidades DINÂMICAS das regras
    
    Fórmula: Pontos = (Pontos_FIA x Fichas) + Bônus_11º - Penalidades
    """
    import ast
    
    # As tabelas de pontos virão das regras aplicáveis (com fallback no serviço de regras)
    
    ress_map = {}
    for _, r in res_df.iterrows():
        try:
            ress_map[r['prova_id']] = ast.literal_eval(r['posicoes'])
        except:
            continue
    
    tipos_prova = dict(zip(prov_df['id'], prov_df['tipo'] if 'tipo' in prov_df.columns else ['Normal']*len(prov_df)))
    temporadas_prova = dict(zip(prov_df['id'], prov_df['temporada'] if 'temporada' in prov_df.columns else [str(datetime.now().year)]*len(prov_df)))
    
    pontos = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta['prova_id']
        
        if prova_id not in ress_map:
            pontos.append(None)
            continue
        
        res = ress_map[prova_id]
        tipo = tipos_prova.get(prova_id, 'Normal')
        temporada_prova = temporadas_prova.get(prova_id, str(datetime.now().year))
        
        # Busca REGRAS DINÂMICAS da temporada (não altera pontos FIA)
        regras = get_regras_aplicaveis(temporada_prova, tipo)
        
        # Seleciona tabela de pontos da regra vigente
        pontos_tabela = regras.get('pontos_posicoes', [])
        n_posicoes = len(pontos_tabela)
        
        # Bônus 11º DINÂMICO da regra
        bonus_11 = regras.get('pontos_11_colocado', 25)
        
        # Dados da aposta (fichas são DINÂMICAS - definidas pelo usuário)
        pilotos = aposta['pilotos'].split(",")
        fichas = list(map(int, aposta['fichas'].split(",")))  # DINÂMICO
        piloto_11 = aposta['piloto_11']
        automatica = int(aposta.get('automatica', 0))
        
        piloto_para_pos = {v: int(k) for k, v in res.items()}
        
        # Cálculo: Pontos da Regra x Fichas (dinâmico)
        sprint_multiplier = 2 if (tipo == 'Sprint' and regras.get('pontos_dobrada')) else 1
        pt = 0
        for i in range(len(pilotos)):
            piloto = pilotos[i]
            ficha = fichas[i] if i < len(fichas) else 0
            pos_real = piloto_para_pos.get(piloto, None)
            
            if pos_real is not None and 1 <= pos_real <= n_posicoes:
                pt += ficha * pontos_tabela[pos_real - 1] * sprint_multiplier
        
        # Bônus 11º colocado (DINÂMICO da regra)
        piloto_11_real = res.get(11, "")
        if piloto_11 == piloto_11_real:
            pt += bonus_11
        
        # Penalidade apostas automáticas consecutivas (DINÂMICA)
        if automatica >= 2:
            pt = round(pt * 0.75, 2)
        
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
        usrs = pd.read_sql('SELECT * FROM usuarios WHERE status = "Ativo"', conn)
        provs = pd.read_sql('SELECT * FROM provas', conn)
        apts = pd.read_sql('SELECT * FROM apostas', conn)
        ress = pd.read_sql('SELECT * FROM resultados', conn)
        
        import ast
        # Se temporada for fornecida, processa apenas provas dessa temporada
        if temporada and 'temporada' in provs.columns:
            provs = provs[provs['temporada'] == temporada]
        
        for _, pr in provs.iterrows():
            pid = pr['id']
            if pid not in ress['prova_id'].values:
                continue
            
            temporada_prova = pr.get('temporada', str(datetime.now().year))
            aps = apts[apts['prova_id'] == pid]
            # Filtra apostas pela temporada se a coluna existir
            if 'temporada' in aps.columns:
                aps = aps[aps['temporada'] == temporada_prova]
            if aps.empty:
                continue
                
            res_row = ress[ress['prova_id'] == pid].iloc[0]
            res_p = ast.literal_eval(res_row['posicoes'])
            piloto_11_real = res_p.get(11, "")
            
            tab = []
            for _, u in usrs.iterrows():
                ap = aps[aps['usuario_id'] == u['id']]
                
                if ap.empty:
                    pontos_val = 0
                    data_envio = None
                    acerto_11 = 0
                else:
                    p_list = calcular_pontuacao_lote(ap, ress, provs)
                    pontos_val = sum(p_list) if p_list else 0
                    data_envio = ap.iloc[0].get('data_envio', None)
                    acerto_11 = 1 if ap.iloc[0]['piloto_11'] == piloto_11_real else 0
                
                tab.append({
                    'usuario_id': u['id'],
                    'pontos': pontos_val,
                    'data_envio': data_envio,
                    'acerto_11': acerto_11
                })
            
            df = pd.DataFrame(tab)
            df['data_envio'] = pd.to_datetime(df['data_envio'], errors='coerce')
            df = df.sort_values(
                by=['pontos', 'acerto_11', 'data_envio'],
                ascending=[False, False, True]
            ).reset_index(drop=True)
            df['posicao'] = df.index + 1
            salvar_classificacao_prova(pid, df, temporada_prova)
