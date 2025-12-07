import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ast
import datetime

from db.db_utils import (
    db_connect, get_user_by_id, get_provas_df, get_pilotos_df, get_apostas_df, get_resultados_df,
    update_user_email, update_user_password, get_user_by_email
)
from services.bets_service import salvar_aposta
from services.auth_service import check_password, hash_password
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

    tabs = st.tabs(["Apostas", "Minha Conta"])
    # ------------------ Aba: Apostas ----------------------
    with tabs[0]:
        st.cache_data.clear()
        # Betting form should show only provas that will occur in the current calendar year
        temporada = st.session_state.get('temporada', str(datetime.datetime.now().year))
        # Fetch all provas (db_utils will filter by temporada when provided). We fetch without filter and
        # then restrict by the prova date to ensure only upcoming/current-year events are shown.
        provas_df = get_provas_df(None)
        try:
            if not provas_df.empty and 'data' in provas_df.columns:
                provas_df['__data_dt'] = pd.to_datetime(provas_df['data'], errors='coerce')
                provas = provas_df[provas_df['__data_dt'].dt.year == current_year]
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

                st.write("Escolha seus pilotos e distribua 15 fichas entre eles (mínimo 3 pilotos de equipes diferentes):")
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
                        st.cache_data.clear()
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
        bonus_11 = 25

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
                    tipo_prova = provas_df[provas_df['id'] == prova_id]['tipo'].values[0] if not provas_df[provas_df['id'] == prova_id].empty else 'Normal'
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
                        pontos_lista = pontos_sprint
                        n_pos = 8
                    else:
                        pontos_lista = pontos_f1
                        n_pos = 10
                    piloto_para_pos = {v: int(k) for k, v in posicoes_dict.items()}
                    for i in range(n_pos):
                        aposta_piloto = pilotos_apostados[i] if i < len(pilotos_apostados) else ""
                        ficha = fichas[i] if i < len(fichas) else 0
                        pos_real = piloto_para_pos.get(aposta_piloto, None)
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
                    piloto_11_real = posicoes_dict.get(11, "")
                    pontos_11_col = bonus_11 if piloto_11_apostado == piloto_11_real else 0
                    total_pontos += pontos_11_col
                    if automatica and int(automatica) >= 2:
                        total_pontos = round(total_pontos * 0.75, 2)
                    st.markdown(f"#### {prova_nome} ({tipo_prova})")
                    st.dataframe(pd.DataFrame(dados), hide_index=True)
                    st.write(f"**11º Apostado:** {piloto_11_apostado} | **11º Real:** {piloto_11_real} | **Pontos 11º:** {pontos_11_col}")
                    st.write(f"**Total de Pontos na Prova:** {total_pontos:.2f}")
                    st.markdown("---")
        else:
            st.info("Nenhuma aposta registrada.")

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
            posicoes_part = df_posicoes[df_posicoes['usuario_id'] == user_id_logado].sort_values('prova_id')
            if not posicoes_part.empty:
                provas_nomes = [provas_df[provas_df['id'] == pid]['nome'].values[0] for pid in posicoes_part['prova_id']]
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
    with tabs[1]:
        st.header("Gestão da Minha Conta")
        st.write(f"Usuário: **{user['nome']}**")
        novo_email = st.text_input("Email cadastrado", value=user['email'])
        st.subheader("Alterar Senha")
        senha_atual = st.text_input("Senha Atual", type="password", key="senha_atual")
        nova_senha = st.text_input("Nova Senha", type="password", key="nova_senha")
        confirma_senha = st.text_input("Confirme Nova Senha", type="password", key="confirma_senha")

        if st.button("Salvar Alterações (Conta)"):
            erros = []
            if not novo_email:
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
                if novo_email != user['email']:
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
                    else:
                        st.error("Falha ao alterar senha.")
                if atualizado:
                    st.rerun()
