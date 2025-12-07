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

def salvar_aposta(
    usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova,
    automatica=0, horario_forcado=None, temporada: str = None
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

    if not pilotos or not fichas or not piloto_11 or len(pilotos) < 3 or sum(fichas) != 15:
        st.error("Dados insuficientes para gerar aposta automática. Revise cadastro de pilotos e equipes.")
        return False

    horario_limite = datetime.strptime(
        f"{data_prova} {horario_prova}", '%Y-%m-%d %H:%M:%S'
    ).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    agora_sp = horario_forcado or datetime.now(ZoneInfo("America/Sao_Paulo"))
    tipo_aposta = 0 if agora_sp <= horario_limite else 1
    dados_aposta = f"Pilotos: {', '.join(pilotos)} | Fichas: {', '.join(map(str, fichas))}"

    usuario = get_user_by_id(usuario_id)
    if not usuario:
        st.error(f"Usuário não encontrado: id={usuario_id}")
        return False

    #if tipo_aposta == 0:
    #    return True
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
                        usuario_id, prova_id, data_envio,
                        ','.join(pilotos),
                        ','.join(map(str, fichas)),
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
                        usuario_id, prova_id, data_envio,
                        ','.join(pilotos),
                        ','.join(map(str, fichas)),
                        piloto_11, nome_prova_bd, automatica
                    )
                )
                conn.commit()
            corpo_email = f"""
            <p>Olá {usuario[1]},</p>
            <p>Sua aposta para a prova <strong>{nome_prova_bd}</strong> foi registrada com sucesso.</p>
            <p>Detalhes:</p>
            <ul>
            <li>Pilotos: {', '.join(pilotos)}</li>
            <li>Fichas: {', '.join(map(str, fichas))}</li>
            <li>Palpite para 11º colocado: {piloto_11}</li>
            </ul>
            <p>Boa sorte!</p>
            """

            enviar_email(usuario[2], f"Aposta registrada - {nome_prova_bd}", corpo_email)

    except Exception as e:
        st.error(f"Erro ao salvar aposta: {str(e)}")
        # rollback handled by context manager when exception propagates; return False
        return False

    registrar_log_aposta(
        apostador=usuario[1],
        aposta=dados_aposta,
        nome_prova=nome_prova_bd,
        piloto_11=piloto_11,
        tipo_aposta=tipo_aposta,
        automatica=automatica,
        horario=agora_sp
    )
    if automatica:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE usuarios SET faltas = faltas + 1 WHERE id=?', (usuario_id,))
            conn.commit()
    return True

def gerar_aposta_aleatoria(pilotos_df):
    import random
    equipes_unicas = [e for e in pilotos_df['equipe'].unique().tolist() if e]
    if len(equipes_unicas) < 3 or pilotos_df.empty or len(pilotos_df['nome'].unique()) < 3:
        st.error(f"Base inválida. Equipes únicas: {equipes_unicas}, Pilotos únicos: {len(pilotos_df['nome'].unique())}")
        return [], [], None
    equipes_selecionadas = random.sample(equipes_unicas, 3)
    pilotos_sel = []
    for equipe in equipes_selecionadas:
        pilotos_equipe = pilotos_df[pilotos_df['equipe'] == equipe]['nome'].tolist()
        if pilotos_equipe:
            piloto_escolhido = random.choice(pilotos_equipe)
            if piloto_escolhido not in pilotos_sel:
                pilotos_sel.append(piloto_escolhido)
    if len(pilotos_sel) < 3:
        st.error(f"Não foi possível selecionar 3 pilotos de equipes diferentes.")
        return [], [], None
    n_pilotos = len(pilotos_sel)
    fichas = [1] * n_pilotos
    total_fichas = 15 - n_pilotos
    for i in range(n_pilotos):
        if total_fichas <= 0:
            break
        max_for_this = min(9, total_fichas)
        add = random.randint(0, max_for_this)
        fichas[i] += add
        total_fichas -= add
    todos_pilotos = pilotos_df['nome'].tolist()
    candidatos_11 = [p for p in todos_pilotos if p not in pilotos_sel]
    piloto_11 = random.choice(candidatos_11) if candidatos_11 else random.choice(todos_pilotos)
    return pilotos_sel, fichas, piloto_11

def gerar_aposta_automatica(usuario_id, prova_id, nome_prova, apostas_df, provas_df):
    try:
        usuario_id = int(usuario_id)
        prova_id = int(prova_id)
    except Exception as e:
        return False, f"IDs inválidos: usuario_id={usuario_id}, prova_id={prova_id}: {e}"
    prova_atual = provas_df[provas_df['id'] == prova_id]
    if prova_atual.empty:
        return False, "Prova não encontrada."
    data_prova = prova_atual['data'].iloc[0]
    horario_prova = prova_atual['horario_prova'].iloc[0]
    horario_limite = datetime.strptime(f"{data_prova} {horario_prova}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    pilotos_df = get_pilotos_df()
    aposta_existente = apostas_df[
        (apostas_df["usuario_id"] == usuario_id) &
        (apostas_df["prova_id"] == prova_id) &
        ((apostas_df["automatica"].isnull()) | (apostas_df["automatica"] == 0))
    ]
    if not aposta_existente.empty:
        return False, "Já existe aposta manual para esta prova."
    prova_ant_id = prova_id - 1
    pilotos_ant, fichas_ant, piloto_11_ant = None, None, None
    prova_ant = provas_df[provas_df['id'] == prova_ant_id]
    if not prova_ant.empty:
        ap_ant = apostas_df[
            (apostas_df['usuario_id'] == usuario_id) &
            (apostas_df['prova_id'] == prova_ant_id)
        ]
        if not ap_ant.empty:
            ap_ant = ap_ant.iloc[0]
            pilotos_ant = ap_ant['pilotos'].split(",")
            fichas_ant = list(map(int, ap_ant['fichas'].split(",")))
            piloto_11_ant = ap_ant['piloto_11']
    if not pilotos_ant or not fichas_ant or not piloto_11_ant:
        pilotos_ant, fichas_ant, piloto_11_ant = gerar_aposta_aleatoria(pilotos_df)
    if not pilotos_ant or not fichas_ant or not piloto_11_ant:
        return False, "Não há dados válidos para gerar aposta automática."
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(automatica) FROM apostas WHERE usuario_id=?', (usuario_id,))
        max_automatica = c.fetchone()[0]
    nova_automatica = 1 if max_automatica is None else max_automatica + 1
    sucesso = salvar_aposta(
        usuario_id, prova_id, pilotos_ant, fichas_ant,
        piloto_11_ant, nome_prova, automatica=nova_automatica, horario_forcado=horario_limite
    )
    return (True, "Aposta automática gerada com sucesso!") if sucesso else (False, "Falha ao salvar aposta automática.")

def calcular_pontuacao_lote(apostas_df, resultados_df, provas_df):
    import ast
    pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]
    bonus_11 = 25
    resultados = {}
    for _, row in resultados_df.iterrows():
        resultados[row['prova_id']] = ast.literal_eval(row['posicoes'])
    tipos_prova = dict(zip(provas_df['id'], provas_df['tipo'] if 'tipo' in provas_df.columns else ['Normal']*len(provas_df)))
    pontos = []
    for _, aposta in apostas_df.iterrows():
        prova_id = aposta['prova_id']
        if prova_id not in resultados:
            pontos.append(None)
            continue
        res = resultados[prova_id]
        pilotos = aposta['pilotos'].split(",")
        fichas = list(map(int, aposta['fichas'].split(",")))
        piloto_11 = aposta['piloto_11']
        automatica = int(aposta.get('automatica', 0))
        pt = 0
        tipo = tipos_prova.get(prova_id, 'Normal')
        if tipo == 'Sprint':
            pontos_lista = pontos_sprint
            n_pos = 8
        else:
            pontos_lista = pontos_f1
            n_pos = 10
        piloto_para_pos = {v: int(k) for k, v in res.items()}
        for i in range(len(pilotos)):
            p = pilotos[i]
            f = fichas[i] if i < len(fichas) else 0
            pos_real = piloto_para_pos.get(p, None)
            if pos_real is not None and 1 <= pos_real <= n_pos:
                pt += f * pontos_lista[pos_real - 1]
        piloto_11_real = res.get(11, "")
        if piloto_11 == piloto_11_real:
            pt += bonus_11
        if automatica and int(automatica) >= 2:
            pt = round(pt * 0.75, 2)
        pontos.append(pt)
    return pontos

def salvar_classificacao_prova(prova_id, df_classificacao, temporada=None):
    """
    Salva classificação de uma prova na tabela posicoes_participantes.
    
    Args:
        prova_id: ID da prova
        df_classificacao: DataFrame com colunas usuario_id, posicao, pontos
        temporada: Ano da temporada (opcional, usa ano atual se não fornecido)
    """
    if temporada is None:
        import datetime
        temporada = str(datetime.datetime.now().year)
    
    with db_connect() as conn:
        cursor = conn.cursor()
        for _, row in df_classificacao.iterrows():
            usuario_id = int(row['usuario_id'])
            posicao = int(row['posicao'])
            pontos_val = float(row['pontos'])
            data_registro = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT OR REPLACE INTO posicoes_participantes 
                (prova_id, usuario_id, posicao, pontos, data_registro, temporada)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (prova_id, usuario_id, posicao, pontos_val, data_registro, temporada))
        conn.commit()

def atualizar_classificacoes_todas_as_provas():
    with db_connect() as conn:
        usuarios_df = pd.read_sql('SELECT * FROM usuarios WHERE status = "Ativo"', conn)
        provas_df = pd.read_sql('SELECT * FROM provas', conn)
        apostas_df = pd.read_sql('SELECT * FROM apostas', conn)
        resultados_df = pd.read_sql('SELECT * FROM resultados', conn)
    for _, prova in provas_df.iterrows():
        prova_id = prova['id']
        # Get temporada from prova if available, otherwise use current year
        temporada = prova.get('temporada', str(pd.Timestamp.now().year))
        if prova_id not in resultados_df['prova_id'].values:
            continue
        apostas_prova = apostas_df[apostas_df['prova_id'] == prova_id]
        if apostas_prova.empty:
            continue
        tabela = []
        for _, usuario in usuarios_df.iterrows():
            aposta = apostas_prova[apostas_prova['usuario_id'] == usuario['id']]
            if aposta.empty:
                pontos = 0
                data_envio = None
                acerto_11 = 0
            else:
                pontos = calcular_pontuacao_lote(aposta, resultados_df, provas_df)
                pontos = pontos[0] if pontos and pontos[0] is not None else 0
                data_envio = aposta.iloc[0]['data_envio'] if 'data_envio' in aposta.columns else None
                acerto_11 = 0
                if not aposta.empty and not resultados_df.empty:
                    resultado = resultados_df[resultados_df['prova_id'] == prova_id]
                    if not resultado.empty:
                        import ast
                        posicoes = ast.literal_eval(resultado.iloc[0]['posicoes'])
                        piloto_11_real = posicoes.get(11, "")
                        piloto_11_apostado = aposta.iloc[0]['piloto_11']
                        if piloto_11_apostado == piloto_11_real:
                            acerto_11 = 1
            tabela.append({
                'usuario_id': int(usuario['id']),
                'pontos': pontos,
                'data_envio': data_envio,
                'acerto_11': acerto_11
            })
        df_classificacao = pd.DataFrame(tabela)
        df_classificacao['data_envio'] = pd.to_datetime(df_classificacao['data_envio'], errors='coerce')
        df_classificacao = df_classificacao.sort_values(
            by=['pontos', 'acerto_11', 'data_envio'],
            ascending=[False, False, True]
        ).reset_index(drop=True)
        df_classificacao['posicao'] = df_classificacao.index + 1
        salvar_classificacao_prova(prova_id, df_classificacao, temporada)
