import streamlit as st
import pandas as pd
import ast

from db.db_schema import db_connect, get_table_columns
from db.repo_races import get_pilotos_df, get_provas_df, get_resultados_df
from services.bets_scoring import atualizar_classificacoes_todas_as_provas
from utils.helpers import render_page_header
from utils.season_utils import get_current_year_str, get_default_season_index, get_season_options

def resultados_view():
    # Verificação de permissão (apenas admin/master)
    if 'token' not in st.session_state or st.session_state.get('user_role') not in ('admin', 'master'):
        st.warning("Acesso restrito a administradores/master.")
        return

    render_page_header(st, "Atualizar Resultado Manualmente")

    # Seletor de temporada
    current_year_str = get_current_year_str()
    temporadas = get_season_options(descending=True)
    default_index = get_default_season_index(temporadas, current_year=current_year_str)
    
    temporada_selecionada = st.selectbox(
        "🗓️ Temporada",
        temporadas,
        index=default_index,
        key="resultados_temporada"
    )
    st.session_state["temporada"] = temporada_selecionada

    # Buscar dados filtrados por temporada
    provas = get_provas_df(temporada_selecionada)
    pilotos_df = get_pilotos_df()
    pilotos_ativos_df = pilotos_df[pilotos_df['status'] == 'Ativo']
    resultados_df = get_resultados_df(temporada_selecionada)

    if len(provas) == 0 or len(pilotos_ativos_df) == 0:
        st.warning("Cadastre provas e pilotos ativos antes de lançar resultados.")
        return

    prova_id = st.selectbox(
        "Selecione a prova",
        provas['id'],
        format_func=lambda x: f"{provas[provas['id'] == x]['nome'].values[0]} ({provas[provas['id'] == x]['tipo'].values[0]})"
    )
    tipo_prova = provas[provas['id'] == prova_id]['tipo'].values[0]
    st.info(f"Tipo da prova selecionada: {tipo_prova}")
    pilotos = pilotos_ativos_df['nome'].tolist()

    # Pré-preencher formulário com resultado existente
    resultado_atual = resultados_df[resultados_df['prova_id'] == prova_id]
    posicoes_existentes = {}
    abandonos_existentes = []
    if not resultado_atual.empty:
        try:
            posicoes_existentes = ast.literal_eval(resultado_atual.iloc[0]['posicoes']) or {}
        except Exception:
            posicoes_existentes = {}
        if 'abandono_pilotos' in resultados_df.columns:
            raw_aband = resultado_atual.iloc[0].get('abandono_pilotos', '')
            if raw_aband is None:
                raw_aband = ''
            abandonos_existentes = [p.strip() for p in str(raw_aband).split(',') if p and p.strip()]

    if st.session_state.get('resultados_prova_sel') != prova_id:
        st.session_state['resultados_prova_sel'] = prova_id
        for pos in range(1, 12):
            st.session_state[f"res_pos_{pos}"] = posicoes_existentes.get(pos, "")
        st.session_state["res_abandonos"] = abandonos_existentes

    posicoes = {}
    st.markdown("**Informe o piloto para cada posição:**")
    col1, col2 = st.columns(2)
    pilotos_usados = set()
    # 1º ao 5º colocados
    for pos in range(1, 6):
        with col1:
            atual = st.session_state.get(f"res_pos_{pos}", "")
            opcoes = [""] + [p for p in pilotos if p not in pilotos_usados or p == atual]
            piloto_sel = st.selectbox(
                f"{pos}º colocado",
                opcoes,
                index=0,
                key=f"res_pos_{pos}"
            )
            if piloto_sel:
                posicoes[pos] = piloto_sel
                pilotos_usados.add(piloto_sel)
    # 6º ao 10º colocados
    for pos in range(6, 11):
        with col2:
            atual = st.session_state.get(f"res_pos_{pos}", "")
            opcoes = [""] + [p for p in pilotos if p not in pilotos_usados or p == atual]
            piloto_sel = st.selectbox(
                f"{pos}º colocado",
                opcoes,
                index=0,
                key=f"res_pos_{pos}"
            )
            if piloto_sel:
                posicoes[pos] = piloto_sel
                pilotos_usados.add(piloto_sel)
    # 11º colocado (qualquer piloto ativo)
    st.markdown("**11º colocado:**")
    piloto_11 = st.selectbox(
        "11º colocado",
        [""] + pilotos,
        index=0,
        key="res_pos_11"
    )
    if piloto_11:
        posicoes[11] = piloto_11

    # Pilotos que abandonaram a prova
    st.markdown("**Pilotos que abandonaram a prova (DNF):**")
    abandono_opcoes = pilotos
    abandono_pilotos = st.multiselect(
        "Selecione todos os pilotos que abandonaram",
        abandono_opcoes,
        key="res_abandonos"
    )

    erro = None
    if st.button("Salvar resultado"):
        # Validação dos campos
        if len(posicoes) < 11 or any(not posicoes.get(pos) for pos in range(1, 11)):
            erro = "Preencha todos os campos de 1º ao 10º colocado (não deixe em branco)."
        elif len(set([posicoes.get(pos) for pos in range(1, 11)])) < 10:
            erro = "Não é permitido repetir piloto entre 1º e 10º colocado."
        elif not posicoes.get(11):
            erro = "Selecione o piloto para 11º colocado."
        # Validação opcional: alertar se algum abandonou e também está em top 11
        conflitos = set(abandono_pilotos) & set([posicoes.get(p) for p in range(1, 12) if posicoes.get(p)])
        if conflitos:
            st.warning(f"Pilotos em conflito (posicionados e como abandono): {', '.join(sorted(conflitos))}")
        if erro:
            st.error(erro)
        else:
            with db_connect() as conn:
                c = conn.cursor()
                # Detecta colunas existentes para inserir corretamente
                cols = get_table_columns(conn, 'resultados')
                abandono_str = ','.join(abandono_pilotos) if abandono_pilotos else ''

                if 'temporada' in cols:
                    c.execute('SELECT 1 FROM resultados WHERE prova_id=%s AND (temporada=%s OR temporada IS NULL)', (prova_id, temporada_selecionada))
                    existe = c.fetchone() is not None
                    if 'abandono_pilotos' in cols:
                        if existe:
                            c.execute(
                                'UPDATE resultados SET posicoes=%s, abandono_pilotos=%s, temporada=%s WHERE prova_id=%s',
                                (str(posicoes), abandono_str, temporada_selecionada, prova_id)
                            )
                        else:
                            c.execute(
                                'INSERT INTO resultados (prova_id, posicoes, abandono_pilotos, temporada) VALUES (%s, %s, %s, %s)',
                                (prova_id, str(posicoes), abandono_str, temporada_selecionada)
                            )
                    else:
                        if existe:
                            c.execute(
                                'UPDATE resultados SET posicoes=%s, temporada=%s WHERE prova_id=%s',
                                (str(posicoes), temporada_selecionada, prova_id)
                            )
                        else:
                            c.execute(
                                'INSERT INTO resultados (prova_id, posicoes, temporada) VALUES (%s, %s, %s)',
                                (prova_id, str(posicoes), temporada_selecionada)
                            )
                else:
                    c.execute('SELECT 1 FROM resultados WHERE prova_id=%s', (prova_id,))
                    existe = c.fetchone() is not None
                    if 'abandono_pilotos' in cols:
                        if existe:
                            c.execute(
                                'UPDATE resultados SET posicoes=%s, abandono_pilotos=%s WHERE prova_id=%s',
                                (str(posicoes), abandono_str, prova_id)
                            )
                        else:
                            c.execute(
                                'INSERT INTO resultados (prova_id, posicoes, abandono_pilotos) VALUES (%s, %s, %s)',
                                (prova_id, str(posicoes), abandono_str)
                            )
                    else:
                        if existe:
                            c.execute(
                                'UPDATE resultados SET posicoes=%s WHERE prova_id=%s',
                                (str(posicoes), prova_id)
                            )
                        else:
                            c.execute(
                                'INSERT INTO resultados (prova_id, posicoes) VALUES (%s, %s)',
                                (prova_id, str(posicoes))
                            )
                conn.commit()
            st.success("Resultado salvo!")
            st.cache_data.clear()
            # Atualiza todas as classificações após editar resultados
            atualizar_classificacoes_todas_as_provas()
            st.rerun()

    st.markdown("---")
    st.subheader(f"Resultados cadastrados - Temporada {temporada_selecionada}")
    resultados_df = get_resultados_df(temporada_selecionada)
    provas_resultados = []
    for _, prova in provas.iterrows():
        res = resultados_df[resultados_df['prova_id'] == prova['id']]
        if not res.empty:
            posicoes_dict = ast.literal_eval(res.iloc[0]['posicoes'])
            linha = {
                "Prova": prova['nome'],
                "Data": pd.to_datetime(prova['data']).strftime("%d/%m/%Y"),
                "Tipo": prova.get('tipo', 'Normal')
            }
            for pos in range(1, 12):
                linha[f"{pos}º"] = posicoes_dict.get(pos, "")
            # Adicionar lista de abandonos se disponível
            if 'abandono_pilotos' in resultados_df.columns:
                linha["Abandonos"] = res.iloc[0].get('abandono_pilotos', '')
            provas_resultados.append(linha)
    if provas_resultados:
        st.dataframe(pd.DataFrame(provas_resultados), width="stretch")
    else:
        st.info("Nenhum resultado cadastrado ainda.")
