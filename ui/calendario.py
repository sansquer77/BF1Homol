import streamlit as st
import pandas as pd
from db.db_utils import get_provas_df
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def main():
    render_page_header(st, "Calendário da Temporada")

    temporadas = get_season_options()
    if not temporadas:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    default_index = get_default_season_index(temporadas)

    temporada = st.selectbox("Temporada", temporadas, index=default_index, key="calendario_temporada")

    provas_df = get_provas_df(temporada)
    if provas_df.empty:
        st.info("Nenhuma prova cadastrada para a temporada selecionada.")
        return

    df = provas_df.copy()
    if 'data' in df.columns:
        df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.sort_values('data_dt')
        df['data'] = df['data_dt'].dt.strftime('%d/%m/%Y')
    if 'horario_prova' not in df.columns:
        df['horario_prova'] = ""
    if 'tipo' not in df.columns:
        df['tipo'] = "Normal"

    df = df.drop(columns=['data_dt'], errors='ignore')

    colunas = {
        'nome': 'Nome',
        'data': 'Data',
        'horario_prova': 'Horário',
        'tipo': 'Tipo'
    }
    df_exibir = df[list(colunas.keys())].rename(columns=colunas)
    st.dataframe(df_exibir, width="stretch")


if __name__ == "__main__":
    main()
