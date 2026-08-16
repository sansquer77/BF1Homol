import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ast

from services.data_access_core import (
    db_connect,
)
from services.data_access_apostas import (
    get_apostas_df,
    get_posicoes_participantes_df,
)
from services.data_access_provas import (
    get_pilotos_df,
    get_provas_df,
    get_resultados_df,
)
from services.data_access_auth import (
    get_user_by_email,
    get_user_by_id,
    update_user_email,
    update_user_password,
)
from services.bets_scoring import calcular_pontuacao_lote
from services.bets_write import gerar_aposta_sem_ideias, salvar_aposta
from services.auth_service import check_password, hash_password
from services.painel_controller import (
    get_proxima_prova_id as _controller_get_proxima_prova_id,
    ordenar_provas_por_calendario as _controller_ordenar_provas_por_calendario,
    parse_data_prova as _controller_parse_data_prova,
    parse_evento_prova_dt as _controller_parse_evento_prova_dt,
)
from services.rules_service import get_regras_aplicaveis
from services.historico_service import calcular_resumo_historico, calcular_dados_grafico
from utils.datetime_utils import now_sao_paulo
from utils.dataframe_contracts import (
    APOSTAS_COLUMNS,
    POSICOES_COLUMNS,
    PROVAS_COLUMNS,
    RESULTADOS_COLUMNS,
    with_required_columns,
)
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def _parse_data_prova(data_raw):
    return _controller_parse_data_prova(data_raw)


def _parse_evento_prova_dt(data_raw, hora_raw, tzinfo):
    return _controller_parse_evento_prova_dt(data_raw, hora_raw, tzinfo)


def _get_proxima_prova_id(provas_df: pd.DataFrame):
    """Retorna o ID da próxima prova (data/hora >= agora em Sao Paulo)."""
    return _controller_get_proxima_prova_id(provas_df)


def _ordenar_provas_por_calendario(provas_df: pd.DataFrame) -> pd.DataFrame:
    """Ordena provas por data/hora do calendário (ascendente), com fallback estável."""
    return _controller_ordenar_provas_por_calendario(provas_df)


# spec: apostas-de-prova v1.2 — critério 10 (validação inline por linha)
def _avisos_inline_aposta(
    pilotos_aposta: list[str],
    pilotos_equipe: dict[str, str],
    permite_mesma_equipe: bool,
) -> list[str]:
    """Avisos imediatos da grade de aposta: piloto repetido e mesma equipe.

    Não substitui as validações do envio; apenas antecipa o feedback.
    Linhas "Nenhum" são ignoradas e a numeração reflete a linha da grade.
    """
    avisos: list[str] = []
    linhas_por_piloto: dict[str, list[int]] = {}
    linhas_por_equipe: dict[str, list[int]] = {}
    for indice, piloto in enumerate(pilotos_aposta):
        if piloto == "Nenhum":
            continue
        numero_linha = indice + 1
        linhas_por_piloto.setdefault(piloto, []).append(numero_linha)
        equipe = pilotos_equipe.get(piloto, "")
        if equipe:
            linhas_por_equipe.setdefault(equipe, []).append(numero_linha)
    for piloto, linhas in linhas_por_piloto.items():
        if len(linhas) > 1:
            avisos.append(
                f"Linhas {', '.join(map(str, linhas))}: piloto repetido ({piloto})."
            )
    if not permite_mesma_equipe:
        for equipe, linhas in linhas_por_equipe.items():
            if len(linhas) > 1:
                avisos.append(
                    f"Linhas {', '.join(map(str, linhas))}: mesma equipe ({equipe})."
                )
    return avisos

def participante_view():
    if 'token' not in st.session_state or 'user_id' not in st.session_state:
        st.warning("Você precisa estar logado para acessar essa página.")
        return

    user = get_user_by_id(st.session_state['user_id'])
    if not user:
        st.error("Usuário não encontrado.")
        return

    render_page_header(st, "Painel do Participante")

    user_role = str(st.session_state.get("user_role", user.get("perfil", "participante"))).strip().lower()
    is_inactive_profile = user_role == "inativo" or str(user.get("status", "")).strip().lower() != "ativo"
    inactive_has_history = bool(st.session_state.get("inactive_has_history", False) or st.session_state.get("allowed_seasons", []))

    allowed_seasons = [
        str(s).strip() for s in (st.session_state.get("allowed_seasons", []) or []) if str(s).strip()
    ]
    if is_inactive_profile and inactive_has_history:
        # Para inativo com histórico, a lista deve refletir apenas temporadas do próprio participante.
        season_options = sorted(set(allowed_seasons))
    else:
        season_options = get_season_options(fallback_years=["2025", "2026"])
    has_season_data = bool(season_options)
    if has_season_data:
        # spec: temporada-global v1.0 — critério 2 (fonte única: seletor da sidebar)
        temporada_global = st.session_state.get("temporada_global", "")
        season = (
            temporada_global if temporada_global in season_options
            else season_options[get_default_season_index(season_options)]
        )
        st.session_state['temporada'] = season
    else:
        if is_inactive_profile and inactive_has_history and allowed_seasons:
            season = allowed_seasons[-1]
            st.session_state['temporada'] = season
        else:
            season = st.session_state.get('temporada', str(now_sao_paulo().year))

        if is_inactive_profile and not inactive_has_history:
            st.info("Não há temporadas com histórico para este usuário inativo.")
        else:
            st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")

    st.write(f"Bem-vindo, {user['nome']} ({user['email']}) - Status: {user['perfil']}")

    force_change = bool(user.get('must_change_password', 0) or st.session_state.get('force_password_change'))
    show_apostas_tab = (not force_change) and (not is_inactive_profile) and has_season_data
    show_historico_tab = (not force_change) and (
        ((not is_inactive_profile) and has_season_data)
        or (is_inactive_profile and inactive_has_history)
    )
    # Aba "Histórico" (consolidado) aparece sempre que o participante tem ao menos uma aposta
    show_historico_geral_tab = not force_change

    if force_change:
        st.warning("⚠️ Você precisa alterar sua senha temporária antes de continuar.")
    elif is_inactive_profile and not inactive_has_history:
        st.info("Usuário inativo sem histórico: apenas Minha Conta está disponível no Painel do Participante.")

    tab_labels = []
    if show_apostas_tab:
        tab_labels.append("Apostas")
    if show_historico_tab:
        # Aba de histórico por temporada, com nome dinâmico mostrando o ano selecionado
        tab_labels.append(f"Apostas - {season}")
    if show_historico_geral_tab:
        # Aba principal de histórico: consolida todas as temporadas do participante.
        tab_labels.append("Histórico")
    tab_labels.append("Minha Conta")
    section_key = "painel_secao_ativa"
    if st.session_state.get(section_key) not in tab_labels:
        st.session_state[section_key] = tab_labels[0]
    active_section = st.radio(
        "Área do painel",
        tab_labels,
        horizontal=True,
        label_visibility="collapsed",
        key=section_key,
    )
    section_container = st.container()

    def _on_prova_change():
        st.session_state["aposta_form_force_reload"] = True
        if "aposta_erros" in st.session_state:
            del st.session_state["aposta_erros"]

    @st.dialog("Regras vigentes")
    def _mostrar_regras_dialog(regras, temporada_sel, tipo_prova_sel):
        is_sprint = str(tipo_prova_sel).strip().lower() == 'sprint'
        regra_sprint = bool(regras.get('regra_sprint'))
        fichas_exibir = regras.get('quantidade_fichas', 15)
        min_pilotos_exibir = regras.get('qtd_minima_pilotos', regras.get('min_pilotos', 3))
        if is_sprint and regra_sprint:
            fichas_exibir = 10
            min_pilotos_exibir = 2

        st.markdown(f"**Temporada:** {temporada_sel}")
        st.markdown(f"**Tipo de prova:** {tipo_prova_sel}")
        st.markdown(f"**Fichas:** {fichas_exibir}")
        st.markdown(f"**Mín. pilotos:** {min_pilotos_exibir}")
        st.markdown(f"**Fichas por piloto:** {regras.get('fichas_por_piloto', '-')}")
        st.markdown(f"**Bônus 11º:** {regras.get('pontos_11_colocado', 25)}")
        st.markdown(f"**Pontos dobrados (Sprint):** {'Sim' if regras.get('pontos_dobrada') else 'Não'}")
        st.markdown(f"**Penalidade abandono:** {'Sim' if regras.get('penalidade_abandono') else 'Não'}")
        if regras.get('penalidade_abandono'):
            st.markdown(f"**Pontos penalidade:** {regras.get('pontos_penalidade', 0)}")

    # fix: inicializa apostas_part, provas_df e resultados_df antes do bloco
    # condicional para evitar NameError nas seções 'Regra de Descarte' e
    # 'Gráfico de Evolução' quando force_change=True.
    temporada = st.session_state.get('temporada', str(now_sao_paulo().year))
    apostas_part = with_required_columns(None, APOSTAS_COLUMNS)
    apostas_df = with_required_columns(None, APOSTAS_COLUMNS)
    provas_df = with_required_columns(None, PROVAS_COLUMNS)
    resultados_df = with_required_columns(None, RESULTADOS_COLUMNS)

    # ------------------ Aba: Apostas ----------------------
    if show_apostas_tab and active_section == "Apostas":
        with section_container:
            temporada = st.session_state.get('temporada', str(now_sao_paulo().year))

            # fix(itens 4 e 5): cada DataFrame é buscado UMA única vez por render
            # e reutilizado em todo o escopo da aba — elimina as 2x get_apostas_df
            # e 3x get_provas_df que existiam antes.
            provas_df = with_required_columns(get_provas_df(temporada), PROVAS_COLUMNS)
            apostas_df = with_required_columns(get_apostas_df(temporada), APOSTAS_COLUMNS)
            resultados_df = with_required_columns(get_resultados_df(temporada), RESULTADOS_COLUMNS)

            try:
                if not provas_df.empty and 'data' in provas_df.columns:
                    provas_ordenadas = _ordenar_provas_por_calendario(provas_df)
                    provas = provas_ordenadas[
                        provas_ordenadas['__data_dt'].apply(
                            lambda x: str(x.year) == str(temporada) if pd.notna(x) else False
                        )
                    ]
                    if not provas.empty:
                        provas = provas.reset_index(drop=True)
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

            if len(provas) > 0 and len(pilotos_df) > 2:
                    prova_ids_validos = set(provas['id'].tolist())
                    proxima_prova_id = _get_proxima_prova_id(provas.to_frame() if isinstance(provas, pd.Series) else provas)
                    temporada_default_aposta = st.session_state.get("aposta_default_temporada")
                    prova_atual_sel = st.session_state.get("sel_prova_aposta")

                    st.markdown("### Etapa 1 de 3 - Selecione a prova")

                    if proxima_prova_id is not None:
                        if temporada_default_aposta != temporada:
                            st.session_state["sel_prova_aposta"] = proxima_prova_id
                            st.session_state["aposta_default_temporada"] = temporada
                        elif prova_atual_sel not in prova_ids_validos:
                            st.session_state["sel_prova_aposta"] = proxima_prova_id

                    col_sel, col_btn, col_sem_ideias = st.columns([6, 1.2, 1.4], vertical_alignment="center")
                    with col_sel:
                        prova_id = st.selectbox(
                            "Escolha a prova",
                            provas['id'],
                            format_func=lambda x: f"{x} - {provas[provas['id'] == x]['nome'].values[0]}"[:40],
                            key="sel_prova_aposta",
                            on_change=_on_prova_change
                        )
                    with col_btn:
                        if st.button("Ver regras"):
                            prova_nome_sel = provas[provas['id'] == prova_id]['nome'].values[0]
                            tipo_raw = provas[provas['id'] == prova_id]['tipo'].values[0] if not provas[provas['id'] == prova_id].empty else 'Normal'
                            tipo_sel = 'Sprint' if str(tipo_raw).strip().lower() == 'sprint' or 'sprint' in str(prova_nome_sel).lower() else 'Normal'
                            regras_sel = get_regras_aplicaveis(temporada, tipo_sel)
                            _mostrar_regras_dialog(regras_sel, temporada, tipo_sel)
                    with col_sem_ideias:
                        feedback_sem_ideias = st.session_state.pop("sem_ideias_feedback", None)
                        if feedback_sem_ideias:
                            st.success(feedback_sem_ideias)
                        if st.button("Sem ideias"):
                            nome_prova_sem_ideias = provas[provas['id'] == prova_id]['nome'].values[0]
                            ok_auto, msg_auto, detalhes_auto = gerar_aposta_sem_ideias(
                                usuario_id=user['id'],
                                prova_id=prova_id,
                                nome_prova=nome_prova_sem_ideias,
                                temporada=temporada,
                            )
                            if ok_auto:
                                # A limpeza global pode não invalidar a função cacheada
                                # já consultada neste mesmo render. Limpa este cache
                                # explicitamente antes do rerun que recarrega o formulário.
                                get_apostas_df.clear()
                                st.session_state["sem_ideias_feedback"] = msg_auto
                                st.session_state["sem_ideias_detalhes"] = detalhes_auto
                                st.session_state["aposta_form_force_reload"] = True
                                st.rerun()
                            else:
                                st.error(msg_auto)
                    nome_prova = provas[provas['id'] == prova_id]['nome'].values[0]
                    tipo_raw = provas[provas['id'] == prova_id]['tipo'].values[0] if not provas[provas['id'] == prova_id].empty else 'Normal'
                    tipo_prova = 'Sprint' if str(tipo_raw).strip().lower() == 'sprint' or 'sprint' in str(nome_prova).lower() else 'Normal'
                    regras = get_regras_aplicaveis(temporada, tipo_prova)
                    quantidade_fichas = int(regras.get('quantidade_fichas', 15))
                    min_pilotos_regra = int(regras.get('qtd_minima_pilotos', regras.get('min_pilotos', 3)))
                    fichas_max_por_piloto = int(regras.get('fichas_por_piloto', quantidade_fichas))
                    permite_mesma_equipe = bool(regras.get('mesma_equipe', False))
                    if {"usuario_id", "prova_id"}.issubset(apostas_df.columns):
                        aposta_existente = apostas_df[
                            (apostas_df['usuario_id'] == user['id']) & (apostas_df['prova_id'] == prova_id)
                        ]
                    else:
                        aposta_existente = with_required_columns(None, APOSTAS_COLUMNS)
                    max_linhas = max(10, int(min_pilotos_regra))
                    pilotos_apostados_ant, fichas_ant, piloto_11_ant = [], [], ""
                    if not aposta_existente.empty:
                        aposta_existente = aposta_existente.iloc[0]
                        pilotos_apostados_ant = aposta_existente['pilotos'].split(",")
                        fichas_ant = list(map(int, aposta_existente['fichas'].split(",")))
                        piloto_11_ant = aposta_existente['piloto_11']
                    else:
                        fichas_ant = []
                        piloto_11_ant = ""

                    detalhes_auto = st.session_state.pop("sem_ideias_detalhes", None)
                    if detalhes_auto and int(detalhes_auto.get("prova_id", 0)) == int(prova_id):
                        pilotos_apostados_ant = [str(p) for p in detalhes_auto.get("pilotos", [])]
                        fichas_ant = [int(f) for f in detalhes_auto.get("fichas", [])]
                        piloto_11_ant = str(detalhes_auto.get("piloto_11", ""))

                    # spec: apostas-de-prova v1.1 — critério 9 (grade única de aposta)
                    df_form_aposta = pd.DataFrame(
                        {
                            "Piloto": [
                                pilotos_apostados_ant[i]
                                if i < len(pilotos_apostados_ant) and pilotos_apostados_ant[i] in pilotos
                                else "Nenhum"
                                for i in range(max_linhas)
                            ],
                            "Fichas": [
                                int(fichas_ant[i]) if i < len(fichas_ant) else 0
                                for i in range(max_linhas)
                            ],
                        }
                    )

                    prova_id_form = st.session_state.get("aposta_form_prova_id")
                    force_reload_form = bool(st.session_state.get("aposta_form_force_reload", False))
                    if prova_id_form != prova_id or force_reload_form:
                        # spec: apostas-de-prova v1.1 — critério 9 (grade única de aposta)
                        # O data_editor não permite atribuir a chave via session_state;
                        # remover a chave faz o widget re-inicializar a partir de `data=`.
                        st.session_state.pop("aposta_editor_data", None)

                        if piloto_11_ant in pilotos:
                            st.session_state["piloto_11"] = piloto_11_ant
                        elif pilotos:
                            st.session_state["piloto_11"] = pilotos[0]

                        st.session_state["aposta_form_prova_id"] = prova_id
                        st.session_state["aposta_form_force_reload"] = False

                    erros_box = st.empty()
                    erros_atuais = st.session_state.get("aposta_erros", [])
                    if erros_atuais:
                        with erros_box:
                            for msg in erros_atuais:
                                st.error(msg)

                    st.markdown("### Etapa 2 de 3 - Monte sua aposta")
                    st.write(
                        f"Escolha seus pilotos e distribua suas fichas entre eles de acordo com as regras "
                        f"(mínimo de {min_pilotos_regra} pilotos com fichas > 0)."
                    )
                    # spec: apostas-de-prova v1.1 — critério 9 (grade única de aposta)
                    editor_data = st.data_editor(
                        df_form_aposta,
                        key="aposta_editor_data",
                        width="stretch",
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "Piloto": st.column_config.SelectboxColumn(
                                "Piloto",
                                options=["Nenhum"] + pilotos,
                                required=True,
                                width="medium",
                            ),
                            "Fichas": st.column_config.NumberColumn(
                                "Fichas",
                                min_value=0,
                                max_value=fichas_max_por_piloto,
                                step=1,
                                default=0,
                                width="small",
                            ),
                        },
                    )
                    pilotos_aposta, fichas_aposta = [], []
                    for _, linha in editor_data.iterrows():
                        piloto_raw = linha["Piloto"]
                        piloto_sel = (
                            "Nenhum" if piloto_raw is None or str(piloto_raw).lower() == "nan"
                            else str(piloto_raw)
                        )
                        fichas_raw = linha["Fichas"]
                        fichas_valor = 0 if fichas_raw is None else int(fichas_raw)
                        pilotos_aposta.append(piloto_sel)
                        fichas_aposta.append(fichas_valor)

                    # spec: apostas-de-prova v1.2 — critério 10 (validação inline por linha)
                    for aviso in _avisos_inline_aposta(pilotos_aposta, pilotos_equipe, permite_mesma_equipe):
                        st.warning(aviso)

                    pilotos_validos = [p for p in pilotos_aposta if p != "Nenhum"]
                    fichas_validas = [f for i, f in enumerate(fichas_aposta) if pilotos_aposta[i] != "Nenhum"]
                    pilotos_com_ficha = [
                        p for i, p in enumerate(pilotos_aposta)
                        if p != "Nenhum" and int(fichas_aposta[i]) > 0
                    ]
                    fichas_com_ficha = [
                        int(f) for i, f in enumerate(fichas_aposta)
                        if pilotos_aposta[i] != "Nenhum" and int(f) > 0
                    ]
                    equipes_apostadas = [pilotos_equipe[p] for p in pilotos_validos]
                    total_fichas = sum(fichas_validas)

                    total_ok = total_fichas == quantidade_fichas
                    total_cor = "#1f9d55" if total_ok else "#c62828"
                    total_status = "Correto" if total_ok else "Incorreto"
                    diferenca_fichas = quantidade_fichas - total_fichas
                    if total_ok:
                        total_detalhe = "total exato"
                    elif diferenca_fichas > 0:
                        total_detalhe = f"faltam {diferenca_fichas}"
                    else:
                        total_detalhe = f"sobram {abs(diferenca_fichas)}"
                    total_message = (
                        f"Total de fichas: {total_fichas}/{quantidade_fichas} "
                        f"({total_status}) — {total_detalhe}"
                    )
                    (st.success if total_ok else st.error)(total_message)

                    pilotos_11_opcoes = [p for p in pilotos if p not in pilotos_validos]
                    if not pilotos_11_opcoes:
                        pilotos_11_opcoes = pilotos
                    if pilotos_11_opcoes:
                        if st.session_state.get("piloto_11") not in pilotos_11_opcoes:
                            st.session_state["piloto_11"] = pilotos_11_opcoes[0]
                    piloto_11 = st.selectbox(
                        "Palpite para 11º colocado", pilotos_11_opcoes,
                        key="piloto_11"
                    )

                    # spec: apostas-de-prova v1.2 — critério 10 (validação inline do 11º)
                    if piloto_11 in pilotos_com_ficha:
                        st.warning(f"O 11º colocado ({piloto_11}) está entre os pilotos apostados.")

                    # spec: apostas-de-prova v1.3 — critério 11 (indicador honesto por validação)
                    sem_duplicados = len(set(pilotos_com_ficha)) == len(pilotos_com_ficha)
                    equipes_com_ficha = [pilotos_equipe[p] for p in pilotos_com_ficha]
                    equipes_ok = permite_mesma_equipe or len(set(equipes_com_ficha)) == len(equipes_com_ficha)
                    max_por_piloto_ok = not fichas_com_ficha or max(fichas_com_ficha) <= fichas_max_por_piloto
                    validacoes_etapa2 = [
                        (
                            len(pilotos_com_ficha) >= min_pilotos_regra,
                            f"Mínimo de {min_pilotos_regra} pilotos com fichas",
                        ),
                        (total_ok, f"Soma exata de {quantidade_fichas} fichas"),
                        (sem_duplicados, "Nenhum piloto repetido"),
                        (
                            equipes_ok,
                            "Nenhuma equipe repetida" if not permite_mesma_equipe else "Equipes (sem restrição)",
                        ),
                        (max_por_piloto_ok, f"Máximo de {fichas_max_por_piloto} fichas por piloto"),
                        (piloto_11 not in pilotos_com_ficha, "11º colocado diferente dos apostados"),
                    ]
                    concluidas_etapa2 = sum(1 for ok_etapa2, _ in validacoes_etapa2 if ok_etapa2)
                    st.progress(
                        concluidas_etapa2 / len(validacoes_etapa2),
                        text=f"Etapa 2: {concluidas_etapa2}/{len(validacoes_etapa2)} validações concluídas",
                    )
                    for ok_etapa2, descricao in validacoes_etapa2:
                        st.markdown(f"- {'[x]' if ok_etapa2 else '[ ]'} {descricao}")

                    st.markdown("### Etapa 3 de 3 - Revise e confirme")
                    st.caption(
                        f"Resumo rapido: {len(pilotos_com_ficha)} pilotos com fichas, "
                        f"total {total_fichas}/{quantidade_fichas}, 11o: {piloto_11}."
                    )

                    if st.button("Efetivar Aposta"):
                        erros = []
                        if len(set(pilotos_com_ficha)) != len(pilotos_com_ficha):
                            erros.append("Não é permitido apostar em dois pilotos iguais.")
                        if not permite_mesma_equipe and len(set(equipes_com_ficha)) < len(equipes_com_ficha):
                            erros.append("Não é permitido apostar em dois pilotos da mesma equipe.")
                        if len(pilotos_com_ficha) < min_pilotos_regra:
                            erros.append(
                                f"Você deve definir fichas para pelo menos {min_pilotos_regra} pilotos. "
                                f"(Atual: {len(pilotos_com_ficha)})"
                            )
                        if total_fichas > quantidade_fichas:
                            erros.append(f"A soma das fichas não pode ser maior que {quantidade_fichas}.")
                        elif total_fichas < quantidade_fichas:
                            faltam = quantidade_fichas - total_fichas
                            erros.append(f"A soma das fichas deve ser exatamente {quantidade_fichas} (faltam {faltam}).")
                        if fichas_com_ficha and max(fichas_com_ficha) > fichas_max_por_piloto:
                            erros.append(f"Máximo de {fichas_max_por_piloto} fichas por piloto.")
                        if piloto_11 in pilotos_com_ficha:
                            erros.append("O 11º colocado não pode ser um dos pilotos apostados.")

                        if erros:
                            st.session_state["aposta_erros"] = erros
                            with erros_box:
                                for msg in erros:
                                    st.error(msg)
                        else:
                            if "aposta_erros" in st.session_state:
                                del st.session_state["aposta_erros"]

                            def _report_aposta_error(msg: str) -> None:
                                st.error(msg)

                            ok = salvar_aposta(
                                user['id'], prova_id, pilotos_com_ficha,
                                fichas_com_ficha, piloto_11, nome_prova,
                                automatica=0,
                                temporada=temporada,
                                error_reporter=_report_aposta_error,
                            )
                            if ok:
                                st.success("Aposta registrada/atualizada!")
            else:
                st.warning("Administração deve cadastrar provas e pilotos antes das apostas.")

    if show_historico_tab and active_section == f"Apostas - {season}":
        with section_container:
            if is_inactive_profile:
                st.info("Usuário inativo: você só pode visualizar suas apostas anteriores.")

            temporada = st.session_state.get('temporada', str(now_sao_paulo().year))
            if apostas_df.empty:
                apostas_df = with_required_columns(get_apostas_df(temporada), APOSTAS_COLUMNS)
            if provas_df.empty:
                provas_df = with_required_columns(get_provas_df(temporada), PROVAS_COLUMNS)
            if resultados_df.empty:
                resultados_df = with_required_columns(get_resultados_df(temporada), RESULTADOS_COLUMNS)

            # --- Exibição detalhada das apostas do participante ---
            st.subheader("Minhas apostas detalhadas")
            # apostas_df, provas_df e resultados_df já foram buscados no topo da aba —
            # apenas reutilizamos as variáveis existentes aqui.
            if {"usuario_id", "prova_id"}.issubset(apostas_df.columns):
                apostas_part = apostas_df[apostas_df['usuario_id'] == user['id']].copy()
            else:
                apostas_part = with_required_columns(apostas_df, APOSTAS_COLUMNS)
            if 'temporada' in apostas_part.columns:
                apostas_part = apostas_part[apostas_part['temporada'] == temporada]
            # fix: só aplica filtro por provas_df quando ele não está vazio;
            # evita descartar todas as apostas quando force_change=True (provas_df = DataFrame()).
            if not provas_df.empty and 'id' in provas_df.columns and 'prova_id' in apostas_part.columns:
                apostas_part = apostas_part[apostas_part['prova_id'].isin(provas_df['id'])]
            if isinstance(apostas_part, pd.DataFrame) and 'prova_id' in apostas_part.columns:
                apostas_part = apostas_part.sort_values(by='prova_id')
            pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
            pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]

            if not apostas_part.empty:
                nomes_abas = [f"{ap['nome_prova']} ({ap['prova_id']})" for _, ap in apostas_part.iterrows()]
                aposta_detalhe = st.selectbox(
                    "Prova detalhada",
                    nomes_abas,
                    key=f"painel_aposta_detalhe_{temporada}",
                )
                detalhe_index = nomes_abas.index(aposta_detalhe)
                for _, aposta in apostas_part.iloc[[detalhe_index]].iterrows():
                    with st.container():
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
                        # Extrair dados de abandono antes de montar a tabela
                        abandonos = set()
                        if regras.get('penalidade_abandono') and not resultado_row.empty and 'abandono_pilotos' in resultado_row.columns:
                            raw_aband = resultado_row.iloc[0].get('abandono_pilotos', '')
                            if raw_aband is None:
                                raw_aband = ''
                            abandonos = {p.strip() for p in str(raw_aband).split(',') if p and p.strip()}
                        
                        dados = []
                        total_pontos = 0
                        if tipo_prova == 'Sprint':
                            pontos_lista = regras.get('pontos_sprint_posicoes') or regras.get('pontos_posicoes') or []
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
                            dnf_status = "DNF" if str(aposta_piloto).strip() in abandonos else "-"
                            dados.append({
                                "Piloto Apostado": aposta_piloto,
                                "Fichas": ficha,
                                "Posição Real": str(pos_real) if pos_real is not None else "-",
                                "DNF": dnf_status,
                                "Pontos": f"{pontos:.2f}"
                            })
                        piloto_11_real = str(posicoes_dict.get(11, "")).strip()
                        bonus_11 = regras.get('pontos_11_colocado', 25)
                        pontos_11_col = bonus_11 if str(piloto_11_apostado).strip() == piloto_11_real else 0
                        total_pontos += pontos_11_col
                        penalidade_abandono = 0
                        pilotos_abandonados = []
                        if abandonos:
                            pilotos_abandonados = [p for p in pilotos_apostados if p.strip() in abandonos]
                            num_aband = len(pilotos_abandonados)
                            penalidade_abandono = int(regras.get('pontos_penalidade', 0)) * num_aband
                            if penalidade_abandono:
                                total_pontos -= penalidade_abandono
                        if tipo_prova == 'Sprint' and regras.get('pontos_dobrada'):
                            total_pontos = total_pontos * 2
                        penalidade_auto = 0
                        if automatica and int(automatica) >= 2:
                            penalidade_auto_percent = regras.get('penalidade_auto_percent', 20)
                            fator = max(0, 1 - (float(penalidade_auto_percent) / 100))
                            desconto = round(total_pontos * fator, 2)
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
                            pilotos_str = ", ".join(pilotos_abandonados)
                            st.write(f"**Penalidade por abandono (DNF):** {pilotos_str} → -{penalidade_abandono} pontos")
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
                if not apostas_part.empty:
                    pontos_por_prova = calcular_pontuacao_lote(apostas_part, resultados_df, provas_df, temporada_descarte=temporada)

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
                df_posicoes = with_required_columns(
                    get_posicoes_participantes_df(temporada), POSICOES_COLUMNS
                )
            except Exception:
                st.info("Nenhum histórico de posições disponível ainda. Quando houver dados, eles aparecerão aqui.")
                df_posicoes = with_required_columns(None, POSICOES_COLUMNS)

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
                    st.plotly_chart(fig_pos, width="stretch")
                else:
                    st.info("Ainda não há histórico de posições para o seu usuário.")
            else:
                st.info("Ainda não há histórico de posições registrado.")

    # ------------------ Aba: Histórico (consolidado multi-temporada) ----------------------
    if show_historico_geral_tab and active_section == "Histórico":
        with section_container:
            _render_historico_geral(user['id'])

    # ---------------- Aba: Minha Conta ----------------------
    if active_section == "Minha Conta":
        with section_container:
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
                    email_cadastrado = get_user_by_email(novo_email)
                    if email_cadastrado and email_cadastrado['id'] != user['id']:
                        erros.append("O email informado já está em uso por outro usuário.")

                if senha_atual or nova_senha or confirma_senha:
                    if not senha_atual:
                        erros.append("Informe a senha atual para alterar a senha.")
                    # fix(crítico): coluna real é `senha_hash` — era `user['senha']` (KeyError silencioso)
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


def _render_historico_geral(usuario_id: int) -> None:
    """Renderiza a aba 'Histórico' com dados consolidados de todas as temporadas.

    Separada em função própria para facilitar leitura, testes e manutenção.

    Estrutura da aba:
    1. Cards de resumo (melhor colocação, pontuação, médias, acertos 11º)
    2. Gráfico de barras: fichas por piloto por temporada
    3. Destaque do piloto mais apostado
    """
    resumo = calcular_resumo_historico(usuario_id)
    dados_grafico = calcular_dados_grafico(usuario_id)

    if not resumo.temporadas_com_dados:
        st.info("Nenhuma aposta encontrada em temporadas anteriores.")
        return

    # ------------------------------------------------------------------
    # Seção 1: Cards de resumo
    # ------------------------------------------------------------------
    st.subheader("🏆 Resumo Histórico")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        melhor_col = resumo.melhor_colocacao
        melhor_col_ano = resumo.melhor_colocacao_ano or "-"
        st.metric(
            label="Melhor Colocação",
            value=f"{melhor_col}º" if melhor_col is not None else "-",
            help=f"Alcançada em {melhor_col_ano}",
        )
        st.caption(f"Ano: {melhor_col_ano}")

    with col2:
        melhor_pt = resumo.melhor_pontuacao
        melhor_pt_ano = resumo.melhor_pontuacao_ano or "-"
        st.metric(
            label="Melhor Pontuação",
            value=f"{melhor_pt:.0f}" if melhor_pt is not None else "-",
            help=f"Obtida em {melhor_pt_ano}",
        )
        st.caption(f"Ano: {melhor_pt_ano}")

    with col3:
        media_pos = resumo.media_posicoes
        st.metric(
            label="Média das Posições",
            value=f"{media_pos:.1f}º" if media_pos is not None else "-",
            help="Média da colocação final por temporada",
        )

    with col4:
        media_pt = resumo.media_pontuacoes
        st.metric(
            label="Média Pontuações",
            value=f"{media_pt:.0f}" if media_pt is not None else "-",
            help="Média da pontuação total por temporada",
        )

    with col5:
        st.metric(
            label="Acertos 11º",
            value=str(resumo.total_acertos_11),
            help="Total de vezes que acertou o 11º colocado em todas as temporadas",
        )

    st.markdown("---")

    # ------------------------------------------------------------------
    # Seção 2: Gráfico de barras — fichas por piloto por temporada
    # ------------------------------------------------------------------
    st.subheader("🏁 Apostas em Pilotos por Temporada")

    fichas_dict = dados_grafico.fichas_por_temporada_piloto

    if not fichas_dict:
        st.info("Ainda não há dados de apostas para exibir o gráfico.")
    else:
        # Transforma a estrutura para: {piloto: {ano: fichas}}
        fichas_por_piloto_ano: dict[str, dict[str, int]] = {}
        for temporada, pilotos_dict in fichas_dict.items():
            for piloto, fichas in pilotos_dict.items():
                if piloto not in fichas_por_piloto_ano:
                    fichas_por_piloto_ano[piloto] = {}
                fichas_por_piloto_ano[piloto][temporada] = fichas

        # Coleta os últimos 5 anos únicos
        todas_temporadas = sorted(fichas_dict.keys())
        anos_selecionados = sorted(todas_temporadas)[-5:] if len(todas_temporadas) > 5 else sorted(todas_temporadas)

        # Ordena pilotos por total de fichas (descendente)
        pilotos_ordenados = sorted(
            fichas_por_piloto_ano.keys(),
            key=lambda p: sum(fichas_por_piloto_ano[p].values()),
            reverse=True
        )

        fig_barras = go.Figure()

        # Adiciona uma série por ano
        for ano in anos_selecionados:
            fichas_por_piloto = [
                fichas_por_piloto_ano[piloto].get(ano, 0)
                for piloto in pilotos_ordenados
            ]
            fig_barras.add_trace(
                go.Bar(
                    name=str(ano),
                    x=pilotos_ordenados,
                    y=fichas_por_piloto,
                    text=[
                        str(f) if f > 0 else ""
                        for f in fichas_por_piloto
                    ],
                    textposition="auto",
                )
            )

        fig_barras.update_layout(
            barmode="group",
            xaxis_title="Piloto",
            yaxis_title="Total de Fichas",
            legend_title="Temporada",
            legend=dict(orientation="v", x=1.02, xanchor="left"),
            margin=dict(r=120),
            height=500,
        )

        st.plotly_chart(fig_barras, width="stretch")

        # ------------------------------------------------------------------
        # Seção 3: Piloto mais apostado
        # ------------------------------------------------------------------
        piloto_top = dados_grafico.piloto_mais_apostado
        fichas_top = dados_grafico.total_fichas_piloto_mais_apostado

        if piloto_top:
            st.markdown(
                f"⭐ **Piloto mais apostado:** {piloto_top} — "
                f"**{fichas_top} fichas** no total ao longo de todas as temporadas."
            )
