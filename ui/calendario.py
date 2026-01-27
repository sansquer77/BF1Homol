import streamlit as st
import pandas as pd
from datetime import datetime
from db.db_utils import get_provas_df
from db.backup_utils import list_temporadas


def main():
    st.title("📅 Calendário da Temporada")

    current_year = str(datetime.now().year)
    try:
        temporadas = list_temporadas() or []
    except Exception:
        temporadas = []

    if not temporadas:
        temporadas = [current_year]

    if current_year in temporadas:
        default_index = temporadas.index(current_year)
    else:
        default_index = 0

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
    st.dataframe(df_exibir, use_container_width=True)


if __name__ == "__main__":
    main()
