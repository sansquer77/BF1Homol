import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from db.db_utils import get_provas_df
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def _parse_horario(value: object) -> tuple[int, int] | None:
    """Converte valores de horario_prova para (hora, minuto)."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("h", ":")
    if ":" not in raw:
        return None
    hh, mm, *_ = raw.split(":")
    if not hh.isdigit() or not mm.isdigit():
        return None
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _build_calendar_events(df: pd.DataFrame) -> list[dict]:
    events: list[dict] = []
    for _, row in df.iterrows():
        dt_value = row.get("data_dt")
        if pd.isna(dt_value):
            continue

        prova_nome = str(row.get("nome", "Prova"))
        tipo = str(row.get("tipo", "Normal") or "Normal").strip().lower()
        horario = _parse_horario(row.get("horario_prova"))
        cor = "#E10600" if tipo == "sprint" else "#1B3A57"

        event = {
            "title": prova_nome,
            "backgroundColor": cor,
            "borderColor": cor,
        }

        if horario:
            start_dt = dt_value.replace(hour=horario[0], minute=horario[1], second=0, microsecond=0)
            end_dt = start_dt + timedelta(hours=2)
            event["start"] = start_dt.isoformat()
            event["end"] = end_dt.isoformat()
        else:
            date_iso = dt_value.date().isoformat()
            event["start"] = date_iso
            event["allDay"] = True

        events.append(event)
    return events


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

    eventos = _build_calendar_events(df)
    hoje_iso = datetime.now().date().isoformat()
    calendar_options = {
        "locale": "pt-br",
        "initialView": "listMonth",
        "initialDate": hoje_iso,
        "height": 680,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listMonth",
        },
        "buttonText": {
            "today": "Hoje",
            "month": "Mês",
            "week": "Semana",
            "day": "Dia",
            "list": "Lista",
        },
        "eventTimeFormat": {
            "hour": "2-digit",
            "minute": "2-digit",
            "hour12": False,
        },
    }

    tab_calendario, tab_horario = st.tabs(["Calendário", "Horário limite"])

    with tab_calendario:
        calendar(events=eventos, options=calendar_options, key=f"calendar_{temporada}")
        st.caption("Calendário inicia em Lista do mês atual; use a barra superior para trocar a visualização.")

    with tab_horario:
        df = df.drop(columns=['data_dt'], errors='ignore')

        colunas = {
            'nome': 'Nome',
            'data': 'Data',
            'horario_prova': 'Horário',
            'tipo': 'Tipo'
        }
        df_exibir = df[list(colunas.keys())].rename(columns=colunas)
        st.dataframe(
            df_exibir,
            width="stretch",
            hide_index=True,
            column_config={
                "Nome": st.column_config.TextColumn("Nome", width="large"),
                "Data": st.column_config.TextColumn("Data", width="small"),
                "Horário": st.column_config.TextColumn("Horário", width="small"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
            },
        )


if __name__ == "__main__":
    main()
