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


def _build_limite_datetime(data_dt: pd.Timestamp | None, horario_value: object) -> datetime | None:
    """Monta datetime limite da prova combinando data e horario_prova."""
    if data_dt is None or pd.isna(data_dt):
        return None

    horario = _parse_horario(horario_value)
    if horario is not None:
        return data_dt.to_pydatetime().replace(hour=horario[0], minute=horario[1], second=0, microsecond=0)

    # Sem horário definido: considera limite no fim do dia da prova.
    return data_dt.to_pydatetime().replace(hour=23, minute=59, second=59, microsecond=0)


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
        now_dt = datetime.now()

        df_horario = df.copy()
        df_horario["limite_dt"] = df_horario.apply(
            lambda row: _build_limite_datetime(row.get("data_dt"), row.get("horario_prova")),
            axis=1,
        )

        futuros = df_horario[df_horario["limite_dt"].notna() & (df_horario["limite_dt"] >= now_dt)]
        proxima_idx = None
        if not futuros.empty:
            proxima_idx = futuros["limite_dt"].sort_values().index[0]

        estado_linha: dict[int, str] = {}
        for idx, row in df_horario.iterrows():
            limite_dt = row.get("limite_dt")
            if limite_dt is not None and not pd.isna(limite_dt) and limite_dt < now_dt:
                estado_linha[idx] = "passada"
            elif proxima_idx is not None and idx == proxima_idx:
                estado_linha[idx] = "proxima"
            else:
                estado_linha[idx] = "normal"

        df_horario = df_horario.drop(columns=['data_dt', 'limite_dt'], errors='ignore')

        colunas = {
            'nome': 'Nome',
            'data': 'Data',
            'horario_prova': 'Horário',
            'tipo': 'Tipo'
        }
        df_exibir = df_horario[list(colunas.keys())].rename(columns=colunas)

        def _style_linha(row: pd.Series) -> list[str]:
            estado = estado_linha.get(row.name, "normal")
            if estado == "passada":
                return ["color: #8B93A1; background-color: #F8FAFC;"] * len(row)
            if estado == "proxima":
                return ["background-color: #FFF7D6; color: #1F2937; font-weight: 700;"] * len(row)
            return [""] * len(row)

        styled_df = df_exibir.style.apply(_style_linha, axis=1)

        st.caption("Provas já encerradas aparecem esmaecidas e a próxima prova fica destacada.")
        st.dataframe(
            styled_df,
            width="stretch",
            hide_index=True,
        )


if __name__ == "__main__":
    main()
