import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ast
import datetime
import re

from db.db_utils import (
    db_connect, get_user_by_id, get_provas_df, get_pilotos_df, get_apostas_df, get_resultados_df,
    update_user_email, update_user_password, get_user_by_email, get_posicoes_participantes_df
)
from services.bets_service import salvar_aposta, calcular_pontuacao_lote, gerar_aposta_sem_ideias
from services.auth_service import check_password, hash_password
from services.rules_service import get_regras_aplicaveis
from utils.datetime_utils import now_sao_paulo, parse_datetime_sao_paulo
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def _parse_data_prova(data_raw):
    """Parse tolerante para datas de prova (yyyy-mm-dd e formatos locais)."""
    if data_raw is None:
        return None
    raw = str(data_raw).strip()
    if not raw:
        return None

    formatos_explicitos = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    )
    for formato in formatos_explicitos:
        parsed = pd.to_datetime(raw, format=formato, errors='coerce')
        if pd.notna(parsed):
            return parsed

    usa_dayfirst = bool(re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$", raw))
    parsed = pd.to_datetime(raw, errors='coerce', dayfirst=usa_dayfirst)
    if pd.notna(parsed):
        return parsed
    return None


def _parse_evento_prova_dt(data_raw, hora_raw, tzinfo):
    data_dt = _parse_data_prova(data_raw)
    if data_dt is None:
        return None

    data_iso = data_dt.strftime("%Y-%m-%d")
    hora = str(hora_raw or "00:00")
    try:
        return parse_datetime_sao_paulo(data_iso, hora)
    except Exception:
        return datetime.datetime(
            data_dt.year,
            data_dt.month,
            data_dt.day,
            0,
            0,
            tzinfo=tzinfo,
        )


def _get_proxima_prova_id(provas_df: pd.DataFrame):
    """Retorna o ID da próxima prova (data/hora >= agora em Sao Paulo).

    fix(item 6): substituído for/iterrows() por df.apply(axis=1) —
    elimina o anti-padrão pandas sem alterar o comportamento.
    """
    if provas_df.empty or 'id' not in provas_df.columns:
        return None

    agora_sp = now_sao_paulo()
    tzinfo = agora_sp.tzinfo

    def _evento_dt(row):
        if row.get('id') is None or not row.get('data'):
            return None
        return _parse_evento_prova_dt(row['data'], row.get('horario_prova', '00:00'), tzinfo)

    evento_dts = provas_df.apply(_evento_dt, axis=1)

    futuras = [
        (dt, row['id'])
        for dt, (_, row) in zip(evento_dts, provas_df.iterrows())
        if dt is not None and dt >= agora_sp
    ]
    passadas = [
        (dt, row['id'])
        for dt, (_, row) in zip(evento_dts, provas_df.iterrows())
        if dt is not None and dt < agora_sp
    ]

    if futuras:
        return min(futuras, key=lambda x: x[0])[1]
    if passadas:
        return max(passadas, key=lambda x: x[0])[1]
    return None


def _ordenar_provas_por_calendario(provas_df: pd.DataFrame) -> pd.DataFrame:
    """Ordena provas por data/hora do calendário (ascendente), com fallback estável."""
    if provas_df.empty:
        return provas_df

    ordered = provas_df.copy()
    tzinfo = now_sao_paulo().tzinfo

    if 'data' in ordered.columns:
        ordered['__data_dt'] = ordered['data'].apply(_parse_data_prova)
        ordered['__evento_dt'] = ordered.apply(
            lambda row: _parse_evento_prova_dt(
                row.get('data'),
                row.get('horario_prova', '00:00'),
                tzinfo,
            ),
            axis=1,
        )
    else:
        ordered['__data_dt'] = pd.NaT
        ordered['__evento_dt'] = pd.NaT

    ordered = ordered.sort_values(
        by=['__evento_dt', '__data_dt', 'id'],
        na_position='last'
    ).reset_index(drop=True)

    return ordered

def participante_view():
    if 'token' not in st.session_state or 'user_id' not in st.session_state:
        st.warning("Você precisa estar logado para acessar essa página.")
        return

    user = get_user_by_id(st.session_state['user_id'])
    if not user:
        st.error("Usuário não encontrado.")
        return

    render_page_header(st, "Painel do Participante")

    season_options = get_season_options(fallback_years=["2025", "2026"])
    if not season_options:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    default_index = get_default_season_index(season_options)

    season = st.selectbox("Temporada", season_options, index=default_index)
    st.session_state['temporada'] = season

    st.write(f"Bem-vindo, {user['nome']} ({user['email']}) - Status: {user['perfil']}")

    force_change = bool(user.get('must_change_password', 0) or st.session_state.get('force_password_change'))
    if force_change:
        st.warning("⚠️ Você precisa alterar sua senha temporária antes de continuar.")
        tabs = st.tabs(["Minha Conta"])
    else:
        tabs = st.tabs(["Apostas", "Minha Conta"])

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
    temporada = st.session_state.get('temporada', str(datetime.datetime.now().year))
    apostas_part = pd.DataFrame()
    provas_df = pd.DataFrame()
    resultados_df = pd.DataFrame()

    # ------------------ Aba: Apostas ----------------------
    if not force_change:
        with tabs[0]:
            temporada = st.session_state.get('temporada', str(datetime.datetime.now().year))

            # fix(itens 4 e 5): cada DataFrame é buscado UMA única vez por render
            # e reutilizado em todo o escopo da aba — elimina as 2x get_apostas_df
            # e 3x get_provas_df que existiam antes.
            provas_df = get_provas_df(temporada)
            apostas_df = get_apostas_df(temporada)
            resultados_df = get_resultados_df(temporada)

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

            if user['status'] == "Ativo":
                if len(provas) > 0 and len(pilotos_df) > 2:
                    prova_ids_validos = set(provas['id'].tolist())
                    proxima_prova_id = _get_proxima_prova_id(provas)
                    temporada_default_aposta = st.session_state.get("aposta_default_temporada")
                    prova_atual_sel = st.session_state.get("sel_prova_aposta")

                    if proxima_prova_id is not None:
                        if temporada_default_aposta != temporada:
                            st.session_state["sel_prova_aposta"] = proxima_prova_id
                            st.session_state["aposta_default_temporada"] = temporada
                        elif prova_atual_sel not in prova_ids_validos:
                            st.session_state["sel_prova_aposta"] = proxima_prova_id

                    col_sel, col_btn, col_sem_ideias = st.columns([6, 1.2, 1.4])
                    with col_sel:
                        prova_id = st.selectbox(
                            "Escolha a prova",
                            provas['id'],
                            format_func=lambda x: f"{x} - {provas[provas['id'] == x]['nome'].values[0]}"[:40],
                            key="sel_prova_aposta",
                            on_change=_on_prova_change
                        )
                    with col_btn:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("Ver regras", width="content"):
                            prova_nome_sel = provas[provas['id'] == prova_id]['nome'].values[0]
                            tipo_raw = provas[provas['id'] == prova_id]['tipo'].values[0] if not provas[provas['id'] == prova_id].empty else 'Normal'
                            tipo_sel = 'Sprint' if str(tipo_raw).strip().lower() == 'sprint' or 'sprint' in str(prova_nome_sel).lower() else 'Normal'
                            regras_sel = get_regras_aplicaveis(temporada, tipo_sel)
                            _mostrar_regras_dialog(regras_sel, temporada, tipo_sel)
                    with col_sem_ideias:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("Sem ideias", width="content"):
                            nome_prova_sem_ideias = provas[provas['id'] == prova_id]['nome'].values[0]
                            ok_auto, msg_auto = gerar_aposta_sem_ideias(
                                usuario_id=user['id'],
                                prova_id=prova_id,
                                nome_prova=nome_prova_sem_ideias,
                                temporada=temporada,
                            )
                            if ok_auto:
                                st.success(msg_auto)
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
                    aposta_existente = apostas_df[
                        (apostas_df['usuario_id'] == user['id']) & (apostas_df['prova_id'] == prova_id)
                    ]
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

                    prova_id_form = st.session_state.get("aposta_form_prova_id")
                    force_reload_form = bool(st.session_state.get("aposta_form_force_reload", False))
                    if prova_id_form != prova_id or force_reload_form:
                        for i in range(max_linhas):
                            st.session_state[f"piloto_aposta_{i}"] = (
                                pilotos_apostados_ant[i]
                                if i < len(pilotos_apostados_ant) and pilotos_apostados_ant[i] in pilotos
                                else "Nenhum"
                            )
                            st.session_state[f"fichas_aposta_{i}"] = int(fichas_ant[i]) if i < len(fichas_ant) else 0

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

                    st.write(
                        f"Escolha seus pilotos e distribua suas fichas entre eles de acordo com as regras "
                        f"(mínimo de {min_pilotos_regra} pilotos com fichas > 0)."
                    )
                    pilotos_aposta, fichas_aposta = [], []
                    min_campos_visiveis = max(1, min(int(min_pilotos_regra), int(max_linhas)))
                    for i in range(max_linhas):
                        mostrar = False
                        if i < min_campos_visiveis:
                            mostrar = True
                        elif i < max_linhas and len([p for p in pilotos_aposta if p != "Nenhum"]) == i and sum(fichas_aposta) < quantidade_fichas:
                            mostrar = True
                        if mostrar:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                key_piloto = f"piloto_aposta_{i}"
                                if key_piloto not in st.session_state:
                                    st.session_state[key_piloto] = (
                                        pilotos_apostados_ant[i]
                                        if len(pilotos_apostados_ant) > i and pilotos_apostados_ant[i] in pilotos
                                        else "Nenhum"
                                    )
                                piloto_sel = st.selectbox(
                                    f"Piloto {i+1}",
                                    ["Nenhum"] + pilotos,
                                    key=key_piloto
                                )
                            with col2:
                                if piloto_sel != "Nenhum":
                                    key_fichas = f"fichas_aposta_{i}"
                                    if key_fichas not in st.session_state:
                                        st.session_state[key_fichas] = int(fichas_ant[i]) if len(fichas_ant) > i else 0
                                    valor_ficha = st.number_input(
                                        f"Fichas para {piloto_sel}", min_value=0, max_value=fichas_max_por_piloto,
                                        key=key_fichas
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
                    st.markdown(
                        (
                            "<div style=\"padding:10px 12px;border-radius:8px;"
                            "border:1px solid #d0d7de;background:#f8f9fa;margin:8px 0 12px 0;\">"
                            "<strong>Total de fichas:</strong> "
                            f"<span style='color:{total_cor};font-weight:700'>{total_fichas}/{quantidade_fichas}</span> "
                            f"<span style='color:{total_cor};font-weight:600'>({total_status})</span> "
                            f"<span style='color:{total_cor};font-weight:600'>- {total_detalhe}</span>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )

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

                    if st.button("Efetivar Aposta"):
                        erros = []
                        if len(set(pilotos_com_ficha)) != len(pilotos_com_ficha):
                            erros.append("Não é permitido apostar em dois pilotos iguais.")
                        equipes_com_ficha = [pilotos_equipe[p] for p in pilotos_com_ficha]
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
                                st.rerun()
                else:
                    st.warning("Administração deve cadastrar provas e pilotos antes das apostas.")
            else:
                st.info("Usuário inativo: você só pode visualizar suas apostas anteriores.")

            # --- Exibição detalhada das apostas do participante ---
            st.subheader("Minhas apostas detalhadas")
            # apostas_df, provas_df e resultados_df já foram buscados no topo da aba —
            # apenas reutilizamos as variáveis existentes aqui.
            apostas_part = apostas_df[apostas_df['usuario_id'] == user['id']]
            if 'temporada' in apostas_part.columns:
                apostas_part = apostas_part[apostas_part['temporada'] == temporada]
            if not provas_df.empty and 'id' in provas_df.columns:
                apostas_part = apostas_part[apostas_part['prova_id'].isin(provas_df['id'])]
            apostas_part = apostas_part.sort_values('prova_id')
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
                            dados.append({
                                "Piloto Apostado": aposta_piloto,
                                "Fichas": ficha,
                                "Posição Real": str(pos_real) if pos_real is not None else "-",
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
                        st.dataframe(pd.DataFrame(dados), hide_index=True, width="stretch")
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
            df_posicoes = get_posicoes_participantes_df(temporada)
        except Exception:
            st.info("Nenhum histórico de posições disponível ainda. Quando houver dados, eles aparecerão aqui.")
            df_posicoes = pd.DataFrame()

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
                email_cadastrado = get_user_by_email(novo_email)
                if email_cadastrado and email_cadastrado['id'] != user['id']:
                    erros.append("O email informado já está em uso por outro usuário.")

            if senha_atual or nova_senha or confirma_senha:
                if not senha_atual:
                    erros.append("Informe a senha atual para alterar a senha.")
                elif not check_password(senha_atual, user['senha']):
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
