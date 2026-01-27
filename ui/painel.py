import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ast
import datetime

from db.db_utils import (
    db_connect, get_user_by_id, get_provas_df, get_pilotos_df, get_apostas_df, get_resultados_df,
    update_user_email, update_user_password, get_user_by_email
)
from services.bets_service import salvar_aposta, calcular_pontuacao_lote
from services.auth_service import check_password, hash_password
from services.rules_service import get_regras_aplicaveis
from db.backup_utils import list_temporadas

def participante_view():
    if 'token' not in st.session_state or 'user_id' not in st.session_state:
        st.warning("Você precisa estar logado para acessar essa página.")
        return

    user = get_user_by_id(st.session_state['user_id'])
    if not user:
        st.error("Usuário não encontrado.")
        return

    col1, col2 = st.columns([1, 16])  # Proporção ajustável conforme aparência desejada
    with col1:
        st.image("BF1.jpg", width=75)
    with col2:
        st.title("Painel do Participante")
        # Season selector (temporada) - read temporadas from the backup-managed table when available
        current_year = datetime.datetime.now().year
        current_year_str = str(current_year)

        try:
            season_options = list_temporadas() or []
        except Exception:
            season_options = []

        # If the temporadas table is empty or missing, fallback to fixed options
        if not season_options:
            season_options = ["2025", "2026"]

        # Default to current year when present, otherwise first option
        if current_year_str in season_options:
            default_index = season_options.index(current_year_str)
        else:
            default_index = 0

        season = st.selectbox("Temporada", season_options, index=default_index)
        st.session_state['temporada'] = season
    
    st.write(f"Bem-vindo, {user['nome']} ({user['email']}) - Status: {user['perfil']}")

    force_change = bool(user.get('must_change_password', 0) or st.session_state.get('force_password_change'))
    if force_change:
        st.warning("⚠️ Você precisa alterar sua senha temporária antes de continuar.")
        tabs = st.tabs(["Minha Conta"])
    else:
        tabs = st.tabs(["Apostas", "Minha Conta"])

    # ------------------ Aba: Apostas ----------------------
    if not force_change:
        with tabs[0]:
            # Betting form should show only provas that will occur in the current calendar year
            temporada = st.session_state.get('temporada', str(datetime.datetime.now().year))
            # Fetch all provas (db_utils will filter by temporada when provided). We fetch without filter and
            # then restrict by the prova date to ensure only upcoming/current-year events are shown.
            provas_df = get_provas_df(temporada)
            try:
                if not provas_df.empty and 'data' in provas_df.columns:
                    provas_df['__data_dt'] = pd.to_datetime(provas_df['data'], errors='coerce')
                    provas = provas_df[provas_df['__data_dt'].apply(lambda x: str(x.year) == str(temporada) if pd.notna(x) else False)]
                else:
                    provas = pd.DataFrame()
            except Exception:
                provas = pd.DataFrame()
            pilotos_df = get_pilotos_df()
            # Filtrar pilotos ativos (com validação de coluna)
            if not pilotos_df.empty:
                if 'status' in pilotos_df.columns:
                    pilotos_ativos_df = pilotos_df[pilotos_df['status'] == 'Ativo']
                else:
                    pilotos_ativos_df = pilotos_df

                pilotos = pilotos_ativos_df['nome'].tolist() if not pilotos_ativos_df.empty else []
                equipes = pilotos_ativos_df['equipe'].tolist() if not pilotos_ativos_df.empty else []
                pilotos_equipe = dict(zip(pilotos, equipes))
            else:
                pilotos = []
                equipes = []
                pilotos_equipe = {}

            if user['status'] == "Ativo":
                if len(provas) > 0 and len(pilotos_df) > 2:
                    prova_id = st.selectbox(
                        "Escolha a prova",
                        provas['id'],
                        format_func=lambda x: provas[provas['id'] == x]['nome'].values[0]
                    )
                    nome_prova = provas[provas['id'] == prova_id]['nome'].values[0]
                    apostas_df = get_apostas_df(temporada)
                    aposta_existente = apostas_df[
                        (apostas_df['usuario_id'] == user['id']) & (apostas_df['prova_id'] == prova_id)
                    ]
                    pilotos_apostados_ant, fichas_ant, piloto_11_ant = [], [], ""
                    if not aposta_existente.empty:
                        aposta_existente = aposta_existente.iloc[0]
                        pilotos_apostados_ant = aposta_existente['pilotos'].split(",")
                        fichas_ant = list(map(int, aposta_existente['fichas'].split(",")))
                        piloto_11_ant = aposta_existente['piloto_11']
                    else:
                        fichas_ant = []
                        piloto_11_ant = ""

                    st.write("Escolha seus pilotos e distribua suas fichas entre eles de acordo com as regras:")
                    max_linhas = 10
                    pilotos_aposta, fichas_aposta = [], []
                    for i in range(max_linhas):
                        mostrar = False
                        if i < 3:
                            mostrar = True
                        elif i < max_linhas and len([p for p in pilotos_aposta if p != "Nenhum"]) == i and sum(fichas_aposta) < 15:
                            mostrar = True
                        if mostrar:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                piloto_sel = st.selectbox(
                                    f"Piloto {i+1}",
                                    ["Nenhum"] + pilotos,
                                    index=(pilotos.index(pilotos_apostados_ant[i]) + 1) if len(pilotos_apostados_ant) > i and pilotos_apostados_ant[i] in pilotos else 0,
                                    key=f"piloto_aposta_{i}"
                                )
                            with col2:
                                if piloto_sel != "Nenhum":
                                    valor_ficha = st.number_input(
                                        f"Fichas para {piloto_sel}", min_value=0, max_value=15,
                                        value=fichas_ant[i] if len(fichas_ant) > i else 0,
                                        key=f"fichas_aposta_{i}"
                                    )
                                else:
                                    valor_ficha = 0
                            pilotos_aposta.append(piloto_sel)
                            fichas_aposta.append(valor_ficha)
                        else:
                            pilotos_aposta.append("Nenhum")
                            fichas_aposta.append(0)

                    pilotos_validos = [p for p in pilotos_aposta if p != "Nenhum"]
                    fichas_validas = [f for i, f in enumerate(fichas_aposta) if pilotos_aposta[i] != "Nenhum"]
                    equipes_apostadas = [pilotos_equipe[p] for p in pilotos_validos]
                    total_fichas = sum(fichas_validas)
                    pilotos_11_opcoes = [p for p in pilotos if p not in pilotos_validos]
                    if not pilotos_11_opcoes:
                        pilotos_11_opcoes = pilotos
                    piloto_11 = st.selectbox(
                        "Palpite para 11º colocado", pilotos_11_opcoes,
                        index=pilotos_11_opcoes.index(piloto_11_ant) if piloto_11_ant in pilotos_11_opcoes else 0
                    )

                    erro = None
                    if st.button("Efetivar Aposta"):
                        if len(set(pilotos_validos)) != len(pilotos_validos):
                            erro = "Não é permitido apostar em dois pilotos iguais."
                        elif len(set(equipes_apostadas)) < len(equipes_apostadas):
                            erro = "Não é permitido apostar em dois pilotos da mesma equipe."
                        elif len(pilotos_validos) < 3:
                            erro = "Você deve apostar em pelo menos 3 pilotos de equipes diferentes."
                        elif total_fichas != 15:
                            erro = "A soma das fichas deve ser exatamente 15."
                        elif piloto_11 in pilotos_validos:
                            erro = "O 11º colocado não pode ser um dos pilotos apostados."
                        if erro:
                            st.error(erro)
                        else:
                            salvar_aposta(
                                user['id'], prova_id, pilotos_validos,
                                fichas_validas, piloto_11, nome_prova, automatica=0, temporada=temporada
                            )
                            st.success("Aposta registrada/atualizada!")
                            st.rerun()
                else:
                    st.warning("Administração deve cadastrar provas e pilotos antes das apostas.")
            else:
                st.info("Usuário inativo: você só pode visualizar suas apostas anteriores.")

            # --- Exibição detalhada das apostas do participante ---
            st.subheader("Minhas apostas detalhadas")
            apostas_df = get_apostas_df(temporada)
            resultados_df = get_resultados_df(temporada)
            provas_df = get_provas_df(temporada)

            apostas_part = apostas_df[apostas_df['usuario_id'] == user['id']].sort_values('prova_id')
            pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
            pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]

            if not apostas_part.empty:
                nomes_abas = [f"{ap['nome_prova']} ({ap['prova_id']})" for _, ap in apostas_part.iterrows()]
                abas = st.tabs(nomes_abas)
                for aba, (_, aposta) in zip(abas, apostas_part.iterrows()):
                    with aba:
                        prova_id = aposta['prova_id']
                        prova_nome = aposta['nome_prova']
                        fichas = list(map(int, aposta['fichas'].split(',')))
                        pilotos_apostados = aposta['pilotos'].split(',')
                        piloto_11_apostado = aposta['piloto_11']
                        automatica = aposta.get('automatica', 0)
                        tipo_raw = provas_df[provas_df['id'] == prova_id]['tipo'].values[0] if not provas_df[provas_df['id'] == prova_id].empty else 'Normal'
                        tipo_prova = 'Sprint' if str(tipo_raw).strip().lower() == 'sprint' or 'sprint' in str(prova_nome).lower() else 'Normal'
                        regras = get_regras_aplicaveis(temporada, tipo_prova)
                        resultado_row = resultados_df[resultados_df['prova_id'] == prova_id]
                        if not resultado_row.empty:
                            try:
                                posicoes_dict = ast.literal_eval(resultado_row.iloc[0]['posicoes'])
                            except Exception:
                                posicoes_dict = {}
                        else:
                            posicoes_dict = {}
                        dados = []
                        total_pontos = 0
                        if tipo_prova == 'Sprint':
                            pontos_lista = regras.get('pontos_sprint_posicoes') or []
                            if not pontos_lista:
                                pontos_lista = pontos_sprint
                        else:
                            pontos_lista = regras.get('pontos_posicoes') or []
                            if not pontos_lista:
                                pontos_lista = pontos_f1
                        n_pos = len(pontos_lista)
                        piloto_para_pos = {str(v).strip(): int(k) for k, v in posicoes_dict.items()}
                        for i in range(n_pos):
                            aposta_piloto = pilotos_apostados[i] if i < len(pilotos_apostados) else ""
                            ficha = fichas[i] if i < len(fichas) else 0
                            pos_real = piloto_para_pos.get(str(aposta_piloto).strip(), None)
                            pontos = 0
                            if pos_real is not None and 1 <= pos_real <= n_pos:
                                pontos = ficha * pontos_lista[pos_real - 1]
                                total_pontos += pontos
                            dados.append({
                                "Piloto Apostado": aposta_piloto,
                                "Fichas": ficha,
                                "Posição Real": pos_real if pos_real is not None else "-",
                                "Pontos": f"{pontos:.2f}"
                            })
                        piloto_11_real = str(posicoes_dict.get(11, "")).strip()
                        bonus_11 = regras.get('pontos_11_colocado', 25)
                        pontos_11_col = bonus_11 if str(piloto_11_apostado).strip() == piloto_11_real else 0
                        total_pontos += pontos_11_col
                        penalidade_abandono = 0
                        if regras.get('penalidade_abandono') and not resultado_row.empty and 'abandono_pilotos' in resultado_row.columns:
                            raw_aband = resultado_row.iloc[0].get('abandono_pilotos', '')
                            if raw_aband is None:
                                raw_aband = ''
                            abandonos = {p.strip() for p in str(raw_aband).split(',') if p and p.strip()}
                            if abandonos:
                                num_aband = sum(1 for p in pilotos_apostados if p.strip() in abandonos)
                                penalidade_abandono = int(regras.get('pontos_penalidade', 0)) * num_aband
                                if penalidade_abandono:
                                    total_pontos -= penalidade_abandono
                        if tipo_prova == 'Sprint' and regras.get('pontos_dobrada'):
                            total_pontos = total_pontos * 2
                        penalidade_auto = 0
                        if automatica and int(automatica) >= 2:
                            desconto = round(total_pontos * 0.75, 2)
                            penalidade_auto = round(total_pontos - desconto, 2)
                            total_pontos = desconto
                        st.markdown(f"#### {prova_nome} ({tipo_prova})")
                        if tipo_prova == 'Sprint':
                            if regras.get('pontos_dobrada'):
                                st.write("**Sprint com pontuação dobrada:** Sim")
                            else:
                                st.write("**Sprint com pontuação dobrada:** Não")
                        st.dataframe(pd.DataFrame(dados), hide_index=True)
                        st.write(f"**11º Apostado:** {piloto_11_apostado} | **11º Real:** {piloto_11_real} | **Pontos 11º:** {pontos_11_col}")
                        if penalidade_abandono:
                            st.write(f"**Penalidade por abandono:** -{penalidade_abandono}")
                        if penalidade_auto:
                            st.write(f"**Penalidade aposta automática:** -{penalidade_auto:.2f}")
                        st.write(f"**Total de Pontos na Prova:** {total_pontos:.2f}")
                        st.markdown("---")
        else:
            st.info("Nenhuma aposta registrada.")

        # --- NOVA SEÇÃO: Prova de Descarte ---
        st.subheader("⚠️ Regra de Descarte")
        regras_temporada = get_regras_aplicaveis(temporada, "Normal")
        descarte_ativo = regras_temporada.get('descarte', False)
        
        if descarte_ativo:
            # Calcular pontuação de todas as provas do participante
            if not apostas_part.empty:
                pontos_por_prova = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df, temporada_descarte=temporada)
                
                # Criar dataframe com provas e pontuações
                provas_pontos = []
                for idx, (_, aposta) in enumerate(apostas_part.iterrows()):
                    if pontos_por_prova[idx] is not None:
                        prova_nome = aposta['nome_prova']
                        prova_id_val = aposta['prova_id']
                        pontos_val = pontos_por_prova[idx]
                        provas_pontos.append({
                            'prova_id': prova_id_val,
                            'nome_prova': prova_nome,
                            'pontos': pontos_val
                        })
                
                if provas_pontos:
                    df_provas_pontos = pd.DataFrame(provas_pontos)
                    # Identificar prova com menor pontuação
                    prova_descarte = df_provas_pontos.loc[df_provas_pontos['pontos'].idxmin()]
                    
                    st.info(
                        f"✅ **Regra de Descarte ATIVA para {temporada}**\n\n"
                        f"Sua prova com **menor pontuação** será descartada no cálculo final do campeonato:\n\n"
                        f"**{prova_descarte['nome_prova']}** - {prova_descarte['pontos']:.2f} pontos\n\n"
                        f"_Esta prova NÃO será contabilizada na sua pontuação final quando o resultado do campeonato for cadastrado._"
                    )
                else:
                    st.info(
                        f"✅ **Regra de Descarte ATIVA para {temporada}**\n\n"
                        f"Quando houver resultados cadastrados, sua prova com menor pontuação será automaticamente descartada no cálculo final do campeonato."
                    )
            else:
                st.info(
                    f"✅ **Regra de Descarte ATIVA para {temporada}**\n\n"
                    f"Quando houver resultados cadastrados, sua prova com menor pontuação será automaticamente descartada no cálculo final do campeonato."
                )
        else:
            st.warning(
                f"❌ **Regra de Descarte NÃO está vigente para {temporada}**\n\n"
                f"Todas as provas serão contabilizadas no cálculo final do campeonato."
            )

        # --------- Gráfico de evolução da posição do participante logado ---------
        st.subheader("Evolução da Posição no Campeonato")
        user_id_logado = user['id']
        user_nome_logado = user['nome']
        try:
            with db_connect() as conn:
                df_posicoes = pd.read_sql('SELECT * FROM posicoes_participantes', conn)
        except Exception:
            st.info("Nenhum histórico de posições disponível ainda. Quando houver dados, eles aparecerão aqui.")
            df_posicoes = pd.DataFrame()

        # Verifica se as colunas existem e só então faz o filtro
        if not df_posicoes.empty and {'usuario_id', 'prova_id', 'posicao'}.issubset(df_posicoes.columns):
            posicoes_part = df_posicoes[df_posicoes['usuario_id'] == user_id_logado]
            if 'temporada' in df_posicoes.columns:
                posicoes_part = posicoes_part[(posicoes_part['temporada'] == temporada) | (posicoes_part['temporada'].isna())]
            else:
                provas_ids_temp = set(provas_df['id'].tolist())
                posicoes_part = posicoes_part[posicoes_part['prova_id'].isin(provas_ids_temp)]
            posicoes_part = posicoes_part.sort_values('prova_id')
            if not posicoes_part.empty:
                provas_nomes = [
                    provas_df[provas_df['id'] == pid]['nome'].values[0]
                    if len(provas_df[provas_df['id'] == pid]) > 0 else f"Prova {pid}"
                    for pid in posicoes_part['prova_id']
                ]
                fig_pos = go.Figure()
                fig_pos.add_trace(go.Scatter(
                    x=provas_nomes,
                    y=posicoes_part['posicao'],
                    mode='lines+markers',
                    name=user_nome_logado if user_nome_logado else "Você"
                ))
                fig_pos.update_yaxes(autorange="reversed")
                fig_pos.update_layout(
                    xaxis_title="Prova",
                    yaxis_title="Posição",
                    title=f"Evolução da Posição - {user_nome_logado if user_nome_logado else 'Você'}",
                    showlegend=False
                )
                st.plotly_chart(fig_pos, use_container_width=True)
            else:
                st.info("Ainda não há histórico de posições para o seu usuário.")
        else:
            st.info("Ainda não há histórico de posições registrado.")

    # ---------------- Aba: Minha Conta ----------------------
    with tabs[0] if force_change else tabs[1]:
        st.header("Gestão da Minha Conta")
        st.write(f"Usuário: **{user['nome']}**")
        novo_email = st.text_input("Email cadastrado", value=user['email'])
        st.subheader("Alterar Senha")
        senha_atual = st.text_input("Senha Atual", type="password", key="senha_atual")
        nova_senha = st.text_input("Nova Senha", type="password", key="nova_senha")
        confirma_senha = st.text_input("Confirme Nova Senha", type="password", key="confirma_senha")

        if st.button("Salvar Alterações (Conta)"):
            erros = []
            if not novo_email or novo_email.strip() == "":
                erros.append("Email não pode ficar vazio.")
            elif novo_email != user['email']:
                # só verifica duplicidade se o email mudou
                email_cadastrado = get_user_by_email(novo_email)
                if email_cadastrado and email_cadastrado['id'] != user['id']:
                    erros.append("O email informado já está em uso por outro usuário.")

            # Troca de senha (opcional)
            if senha_atual or nova_senha or confirma_senha:
                if not senha_atual:
                    erros.append("Informe a senha atual para alterar a senha.")
                elif not check_password(senha_atual, user['senha_hash']):
                    erros.append("Senha atual incorreta.")
                elif not nova_senha:
                    erros.append("Informe a nova senha.")
                elif nova_senha != confirma_senha:
                    erros.append("Nova senha e confirmação não coincidem.")

            if erros:
                for erro in erros:
                    st.error(erro)
            else:
                atualizado = False
                if novo_email and novo_email.strip() != "" and novo_email != user['email']:
                    if update_user_email(user['id'], novo_email):
                        st.success("Email atualizado!")
                        atualizado = True
                    else:
                        st.error("Falha ao atualizar email.")
                if nova_senha:
                    senha_hash = hash_password(nova_senha)
                    if update_user_password(user['id'], senha_hash):
                        st.success("Senha alterada!")
                        atualizado = True
                        st.session_state['force_password_change'] = False
                    else:
                        st.error("Falha ao alterar senha.")
                if atualizado:
                    st.rerun()
