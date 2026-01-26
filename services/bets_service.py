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

def pode_fazer_aposta(data_prova_str, horario_prova_str, horario_usuario=None):
    """
    Verifica se o usuário pode fazer aposta comparando horário local com horário de São Paulo.
    """
    try:
        # Horário limite em São Paulo
        horario_limite_sp = datetime.strptime(
            f"{data_prova_str} {horario_prova_str}", '%Y-%m-%d %H:%M:%S'
        ).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

        # Horário do usuário (padrão: agora em SP)
        if horario_usuario is None:
            horario_usuario = datetime.now(ZoneInfo("America/Sao_Paulo"))
        elif not horario_usuario.tzinfo:
            # Se sem timezone, assume SP
            horario_usuario = horario_usuario.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

        # Converte para UTC para comparar
        horario_usuario_utc = horario_usuario.astimezone(ZoneInfo("UTC"))
        horario_limite_utc = horario_limite_sp.astimezone(ZoneInfo("UTC"))

        pode = horario_usuario_utc <= horario_limite_utc
        mensagem = f"Aposta {'permitida' if pode else 'bloqueada'} (Horário limite SP: {horario_limite_sp.strftime('%d/%m/%Y %H:%M:%S')})"

        return pode, mensagem, horario_limite_sp
    except Exception as e:
        return False, f"Erro ao validar horário: {str(e)}", None

def salvar_aposta(
    usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova,
    automatica=0, horario_forcado=None, temporada: str | None = None
):
    # Garante tipo correto para os argumentos IDs (resolve erro de usuário não encontrado)
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        st.error(f"IDs inválidos: usuario_id={usuario_id}, prova_id={prova_id} ({e})")
        return False

    nome_prova_bd, data_prova, horario_prova = get_horario_prova(prova_id)
    if not horario_prova or not nome_prova_bd or not data_prova:
        st.error("Prova não encontrada ou horário/nome/data não cadastrados.")
        return False

    # Obter regras para validação
    tipo_prova_regra = "Sprint" if "Sprint" in (nome_prova_bd or "") else "Normal"
    regras = get_regras_aplicaveis(str(temporada or datetime.now().year), tipo_prova_regra)
    
    quantidade_fichas = regras.get('quantidade_fichas', 15)
    min_pilotos = regras.get('min_pilotos', 3)

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < min_pilotos or sum(fichas) != quantidade_fichas:
        st.error(f"Dados insuficientes para gerar aposta. Regra: {min_pilotos} pilotos e {quantidade_fichas} fichas.")
        return False

    horario_limite = datetime.strptime(
        f"{data_prova} {horario_prova}", '%Y-%m-%d %H:%M:%S'
    ).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

    agora_sp = horario_forcado or datetime.now(ZoneInfo("America/Sao_Paulo"))
    tipo_aposta = 0 if agora_sp <= horario_limite else 1

    dados_pilotos = ', '.join(pilotos)
    dados_fichas = ', '.join(map(str, fichas))

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        st.error(f"Usuário não encontrado: id={usuario_id}")
        return False

    try:
        with db_connect() as conn:
            c = conn.cursor()
            # Detect if temporada column exists and include it in queries when present
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

            # Enviar confirmação por email (opcional, pode falhar)
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
    
    equipes_selecionadas = random.sample(equipes_unicas, 3)
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
        if pilotos_equipe:
            pilotos_sel.append(random.choice(pilotos_equipe))
            
    if len(pilotos_sel) < 3:
        return [], [], None
        
    fichas = [1] * 3
    total_fichas = 12 # Assume padrão 15
    for i in range(3):
        add = random.randint(0, min(9, total_fichas))
        fichas[i] += add
        total_fichas -= add
        
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
    horario_limite = datetime.strptime(f"{data_prova} {horario_prova}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    
    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id) & 
        (apostas_df["prova_id"] == prova_id) & 
        ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."
        
    # Tentar pegar aposta da prova anterior
    prova_ant_id = prova_id - 1
    ap_ant = apostas_df[(apostas_df['usuario_id'] == usuario_id) & (apostas_df['prova_id'] == prova_ant_id)]
    
    if not ap_ant.empty:
        ap_ant = ap_ant.iloc[0]
        pilotos_ant = ap_ant['pilotos'].split(",")
        fichas_ant = list(map(int, ap_ant['fichas'].split(",")))
        piloto_11_ant = ap_ant['piloto_11']
    else:
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria(get_pilotos_df())
        
    if not pilotos_ant:
        return False, "Não há dados válidos para gerar aposta automática."
        
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(automatica) FROM apostas WHERE usuario_id=?', (usuario_id,))
        max_auto = c.fetchone()[0] or 0
        nova_auto = 1 if max_auto is None else max_auto + 1
        
    sucesso = salvar_aposta(
        usuario_id, prova_id, pilotos_ant, fichas_ant, piloto_11_ant, nome_prova,
        automatica=nova_auto, horario_forcado=horario_limite, temporada=temporada
    )
    
    return (True, "Aposta automática gerada!") if sucesso else (False, "Falha ao salvar.")

def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação de um lote de apostas respeitando as regras da temporada.
    
    Args:
        ap_df: DataFrame de apostas
        res_df: DataFrame de resultados
        prov_df: DataFrame de provas
        temporada_descarte: Temporada para aplicar descarte (None = usa aposta.temporada)
    
    Returns:
        Lista de pontos calculados, respeitando:
        - Fórmula: fichas[i] × pontos_piloto[posição[i]-1] + bônus_11
        - Descarte: remove pior resultado se habilitado na regra
        - Penalidade: deduz pontos por abandono
        - Wildcard: multiplica por 2 se sprint com pontos_dobrada=Sim
    """
    import ast
    ress_map = {r['prova_id']: ast.literal_eval(r['posicoes']) for _, r in res_df.iterrows()}
    tipos_prova = dict(zip(prov_df['id'], prov_df['tipo'] if 'tipo' in prov_df.columns else ['Normal']*len(prov_df)))
    
    pontos = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta['prova_id']
        if prova_id not in ress_map:
            pontos.append(None)
            continue
            
        res = ress_map[prova_id]
        tipo = tipos_prova.get(prova_id, 'Normal')
        temp_str = str(aposta.get('temporada', datetime.now().year))
        regras = get_regras_aplicaveis(temp_str, tipo)
        
        pilotos = aposta['pilotos'].split(",")
        fichas = list(map(int, aposta['fichas'].split(",")))
        piloto_11 = aposta['piloto_11']
        
        pts_pos = regras.get('pontos_posicoes', [])
        p_pos = {v: int(k) for k, v in res.items()}
        
        # Calculo base: fichas × pontos_posição + bônus_11
        pt = 0
        for i in range(min(len(pilotos), len(fichas))):
            piloto = pilotos[i]
            ficha = fichas[i]
            if piloto in p_pos and 1 <= p_pos[piloto] <= len(pts_pos):
                pos = p_pos[piloto]
                pts_piloto = pts_pos[pos - 1]
                pt += ficha * pts_piloto
        
        # Bônus 11º colocado
        if piloto_11 == res.get(11):
            pt += regras.get('pontos_11_colocado', 0)
        
        # Wildcard (pontuação dobrada em provas Sprint)
        if regras.get('dobrada', False) and tipo == 'Sprint':
            pt *= 2
        
        # Aposta automática com fator de redução (legado - manter compatibilidade)
        if int(aposta.get('automatica', 0)) >= 2:
            pt *= 0.75
        
        pontos.append(round(pt, 2))
    
    return pontos

def aplicar_descarte_temporada(user_id: int, temporada: str, regra: dict) -> float:
    """
    Aplica descarte do pior resultado se habilitado na regra.
    
    Args:
        user_id: ID do usuário
        temporada: String da temporada
        regra: Dict com regra vigente (contém 'descarte': bool)
    
    Returns:
        Pontos totais após descarte
    """
    if not regra.get('descarte', False):
        # Sem descarte, retorna suma total
        with db_connect() as conn:
            df = pd.read_sql(
                'SELECT SUM(pontos) as total FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?',
                conn,
                params=(user_id, str(temporada))
            )
            return float(df['total'].iloc[0] or 0)
    
    # Com descarte, remove pior resultado
    with db_connect() as conn:
        df = pd.read_sql(
            'SELECT pontos FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ? ORDER BY pontos ASC LIMIT 1',
            conn,
            params=(user_id, str(temporada))
        )
        pior = float(df['pontos'].iloc[0] or 0) if not df.empty else 0
        
        df_total = pd.read_sql(
            'SELECT SUM(pontos) as total FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?',
            conn,
            params=(user_id, str(temporada))
        )
        total = float(df_total['total'].iloc[0] or 0)
        return max(0, total - pior)

def aplicar_penalidade_abandono(user_id: int, prova_id: int, regra: dict) -> None:
    """
    Aplica penalidade por abandono de piloto(s) na aposta, se habilitado na regra.
    
    Args:
        user_id: ID do usuário
        prova_id: ID da prova
        regra: Dict com regra vigente (contém 'penalidade_abandono': bool, 'pontos_penalidade': int)
    """
    if not regra.get('penalidade_abandono', False):
        return
    
    # TODO: Implementar lógica de detecção de abandono e aplicação de penalidade
    # Esta função deve:
    # 1. Verificar se algum piloto apostado não completou a prova (status = abandono)
    # 2. Deduzir 'pontos_penalidade' dos pontos da aposta
    pass

def salvar_classificacao_prova(p_id, df_c, temp=None):
    """
    Salva a classificação de uma prova na tabela posicoes_participantes.
    
    Args:
        p_id: ID da prova
        df_c: DataFrame com colunas usuario_id, posicao, pontos
        temp: Temporada (string). Se None, usa ano atual.
    """
    if temp is None:
        temp = str(datetime.now().year)
    
    with db_connect() as conn:
        c = conn.cursor()
        # Verificar se coluna temporada existe
        c.execute("PRAGMA table_info('posicoes_participantes')")
        cols = [r[1] for r in c.fetchall()]
        has_temporada = 'temporada' in cols
        
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

def atualizar_classificacoes_todas_as_provas():
    """
    Recalcula e atualiza as classificações de todas as provas com resultados cadastrados.
    Respeita a temporada de cada prova para cálculo correto.
    """
    with db_connect() as conn:
        usrs = pd.read_sql('SELECT * FROM usuarios WHERE status = "Ativo"', conn)
        provs = pd.read_sql('SELECT * FROM provas', conn)
        apts = pd.read_sql('SELECT * FROM apostas', conn)
        ress = pd.read_sql('SELECT * FROM resultados', conn)
        
        import ast
        for _, pr in provs.iterrows():
            pid = pr['id']
            
            # Verificar se há resultado para esta prova
            if pid not in ress['prova_id'].values:
                continue
            
            # Obter temporada da prova (usa ano atual se não existir)
            temporada_prova = pr.get('temporada', str(datetime.now().year))
            
            # Filtrar apostas para esta prova
            aps = apts[apts['prova_id'] == pid]
            if aps.empty:
                continue
                
            res_row = ress[ress['prova_id'] == pid].iloc[0]
            res_p = ast.literal_eval(res_row['posicoes'])
            
            tab = []
            for _, u in usrs.iterrows():
                # Filtrar apostas do usuário para esta prova
                ap = aps[aps['usuario_id'] == u['id']]
                
                # Calcular pontos usando a temporada correta
                p_list = calcular_pontuacao_lote(ap, ress, provs)
                p = p_list[0] if p_list and p_list[0] is not None else 0
                
                # Verificar acerto do 11º colocado
                acerto_11 = 0
                if not ap.empty:
                    if ap.iloc[0]['piloto_11'] == res_p.get(11):
                        acerto_11 = 1
                        
                tab.append({
                    'usuario_id': u['id'],
                    'pontos': p,
                    'acerto_11': acerto_11
                })
            
            # Ordenar por pontos (desc) e acerto_11 (desc) como desempate
            df = pd.DataFrame(tab).sort_values(by=['pontos', 'acerto_11'], ascending=False).reset_index(drop=True)
            df['posicao'] = df.index + 1
            
            # Salvar com temporada correta
            salvar_classificacao_prova(pid, df, temporada_prova)
