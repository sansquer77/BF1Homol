import streamlit as st
import pandas as pd
import ast
from datetime import datetime

from db.db_utils import db_connect, get_provas_df, get_pilotos_df, get_resultados_df
from db.backup_utils import list_temporadas
from services.bets_service import atualizar_classificacoes_todas_as_provas

def resultados_view():
    # Verificação de permissão (apenas admin/master)
    if 'token' not in st.session_state or st.session_state.get('user_role') not in ('admin', 'master'):
        st.warning("Acesso restrito a administradores/master.")
        return

    st.title("Atualizar Resultado Manualmente")

    # Seletor de temporada
    current_year = datetime.now().year
    current_year_str = str(current_year)
    try:
        temporadas = list_temporadas() or []
    except Exception:
        temporadas = []
    if not temporadas:
        temporadas = [current_year_str]
    if current_year_str not in temporadas:
        temporadas.append(current_year_str)
    temporadas = sorted(temporadas, reverse=True)
    default_index = temporadas.index(current_year_str) if current_year_str in temporadas else 0
    
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

    posicoes = {}
    st.markdown("**Informe o piloto para cada posição:**")
    col1, col2 = st.columns(2)
    pilotos_usados = set()
    # 1º ao 5º colocados
    for pos in range(1, 6):
        with col1:
            opcoes = [""] + [p for p in pilotos if p not in pilotos_usados]
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
            opcoes = [""] + [p for p in pilotos if p not in pilotos_usados]
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

    erro = None
    if st.button("Salvar resultado"):
        # Validação dos campos
        if len(posicoes) < 11 or any(not posicoes.get(pos) for pos in range(1, 11)):
            erro = "Preencha todos os campos de 1º ao 10º colocado (não deixe em branco)."
        elif len(set([posicoes.get(pos) for pos in range(1, 11)])) < 10:
            erro = "Não é permitido repetir piloto entre 1º e 10º colocado."
        elif not posicoes.get(11):
            erro = "Selecione o piloto para 11º colocado."
        if erro:
            st.error(erro)
        else:
            with db_connect() as conn:
                c = conn.cursor()
                c.execute(
                    'REPLACE INTO resultados (prova_id, posicoes) VALUES (?, ?)',
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
            provas_resultados.append(linha)
    if provas_resultados:
        st.dataframe(pd.DataFrame(provas_resultados))
    else:
        st.info("Nenhum resultado cadastrado ainda.")
