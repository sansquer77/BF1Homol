"""Módulo de Calendário da Temporada.

Regras de timezone:
    - O banco de dados armazena todos os horários em America/Sao_Paulo (sem
      conversão automática pelo driver).  Os valores lidos são, portanto,
      "naive" mas implícita e canonicamente SAÕ PAULO.
    - Este módulo lê esses valores, ATRIBUI o fuso America/Sao_Paulo a eles
      (via localize) e converte para o timezone selecionado pelo usuário
      APENAS para exibição.  Nada é gravado no banco.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+; requer tzdata no requirements.txt
from streamlit_calendar import calendar
from services.data_access_provas import get_provas_df
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TZ_ORIGEM = "America/Sao_Paulo"  # timezone canônico do banco de dados

# Timezones oferecidos no seletor.  A lista cobre os fusos mais relevantes
# para o público-alvo (Brasil + fusos internacionais comuns).
TIMEZONES_OPCOES: list[str] = [
    "America/Sao_Paulo",
    "America/Fortaleza",
    "America/Manaus",
    "America/Belem",
    "America/Noronha",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "America/Buenos_Aires",
    "Europe/London",
    "Europe/Lisbon",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "Europe/Madrid",
    "Asia/Dubai",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Australia/Sydney",
    "UTC",
]


# ---------------------------------------------------------------------------
# Helpers de timezone
# ---------------------------------------------------------------------------

def _localizar_e_converter(dt_naive: datetime, tz_destino: str) -> datetime:
    """Atribui o fuso de origem (SAÕ PAULO) ao datetime naive do BD e converte
    para o fuso de destino.

    Args:
        dt_naive: datetime sem tzinfo, lido do banco (implicitamente SP).
        tz_destino: string IANA do timezone de destino, ex. 'Europe/London'.

    Returns:
        datetime com tzinfo do destino.
    """
    tz_sp = ZoneInfo(TZ_ORIGEM)
    tz_dst = ZoneInfo(tz_destino)
    dt_sp = dt_naive.replace(tzinfo=tz_sp)   # localiza sem deslocar o horário
    return dt_sp.astimezone(tz_dst)           # converte para o destino


def _formatar_horario(dt_aware: datetime) -> str:
    """Formata datetime para 'HH:MM' respeitando o tzinfo embutido."""
    return dt_aware.strftime("%H:%M")


def _offset_label(tz_name: str) -> str:
    """Retorna um label no formato 'America/Sao_Paulo (UTC-03:00)' para o seletor."""
    try:
        agora = datetime.now(ZoneInfo(tz_name))
        offset = agora.utcoffset()
        total_minutos = int(offset.total_seconds() // 60)
        sinal = "+" if total_minutos >= 0 else "-"
        hh, mm = divmod(abs(total_minutos), 60)
        return f"{tz_name} (UTC{sinal}{hh:02d}:{mm:02d})"
    except Exception:
        return tz_name


# ---------------------------------------------------------------------------
# Helpers de parsing de dados brutos
# ---------------------------------------------------------------------------

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
    hour, minute = int(hh), int(mm)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def _build_dt_sp(data_dt: pd.Timestamp, horario_value: object) -> datetime | None:
    """Constrói um datetime com fuso America/Sao_Paulo a partir dos campos brutos.

    Args:
        data_dt: Timestamp da data da prova.
        horario_value: Valor bruto do campo horario_prova.

    Returns:
        datetime aware (America/Sao_Paulo) ou None se data inválida.
    """
    if data_dt is None or pd.isna(data_dt):
        return None

    horario = _parse_horario(horario_value)
    if horario is not None:
        dt_naive = data_dt.to_pydatetime().replace(
            hour=horario[0], minute=horario[1], second=0, microsecond=0
        )
    else:
        # Sem horário: usa 23:59:59 como limite conservador do dia
        dt_naive = data_dt.to_pydatetime().replace(hour=23, minute=59, second=59, microsecond=0)

    return dt_naive.replace(tzinfo=ZoneInfo(TZ_ORIGEM))


# ---------------------------------------------------------------------------
# Construtores de dados para as abas
# ---------------------------------------------------------------------------

def _build_calendar_events(df: pd.DataFrame, tz_destino: str) -> list[dict]:
    """Gera lista de eventos para o componente streamlit-calendar.

    Os horários são convertidos para o timezone de destino antes de serializar.

    Args:
        df: DataFrame com as provas, já com coluna data_dt (Timestamp naive SP).
        tz_destino: Timezone selecionado pelo usuário.

    Returns:
        Lista de dicionários de eventos compatíveis com FullCalendar.
    """
    events: list[dict] = []
    for _, row in df.iterrows():
        data_dt = row.get("data_dt")
        if pd.isna(data_dt):
            continue

        prova_nome = str(row.get("nome", "Prova"))
        tipo = str(row.get("tipo", "Normal") or "Normal").strip().lower()
        cor = "#E10600" if tipo == "sprint" else "#1B3A57"
        horario = _parse_horario(row.get("horario_prova"))

        event: dict = {
            "title": prova_nome,
            "backgroundColor": cor,
            "borderColor": cor,
        }

        if horario:
            dt_naive = data_dt.to_pydatetime().replace(
                hour=horario[0], minute=horario[1], second=0, microsecond=0
            )
            dt_destino = _localizar_e_converter(dt_naive, tz_destino)
            end_dt = dt_destino + timedelta(hours=2)
            event["start"] = dt_destino.isoformat()
            event["end"] = end_dt.isoformat()
        else:
            event["start"] = data_dt.date().isoformat()
            event["allDay"] = True

        events.append(event)
    return events


def _build_tabela_horario(
    df_temporada: pd.DataFrame,
    tz_destino: str,
    now_aware: datetime,
) -> tuple[pd.DataFrame, dict[int, str]]:
    """Prepara o DataFrame de exibição da aba 'Horário limite'.

    Converte os horários para o timezone de destino e classifica cada linha
    como 'passada', 'proxima' ou 'normal' para o estilo visual.

    Args:
        df_temporada: Provas já filtradas pela temporada selecionada.
        tz_destino: Timezone de exibição.
        now_aware: Datetime atual com tzinfo (usado para comparar com limite).

    Returns:
        Tupla (DataFrame formatado para exibir, dict {index: estado}).
    """
    df = df_temporada.copy()

    # Monta datetime aware (SP) e converte para o destino
    df["limite_sp"] = df.apply(
        lambda row: _build_dt_sp(row.get("data_dt"), row.get("horario_prova")), axis=1
    )
    df["limite_dest"] = df["limite_sp"].apply(
        lambda dt: dt.astimezone(ZoneInfo(tz_destino)) if dt is not None else None
    )

    # Determina próxima prova
    futuros = df[df["limite_dest"].notna() & (df["limite_dest"] >= now_aware)]
    proxima_idx = futuros["limite_dest"].sort_values().index[0] if not futuros.empty else None

    estado_linha: dict[int, str] = {}
    for idx, row in df.iterrows():
        lim = row["limite_dest"]
        if lim is not None and lim < now_aware:
            estado_linha[idx] = "passada"
        elif proxima_idx is not None and idx == proxima_idx:
            estado_linha[idx] = "proxima"
        else:
            estado_linha[idx] = "normal"

    # Formata colunas de exibição
    df["horario_exibir"] = df["limite_dest"].apply(
        lambda dt: _formatar_horario(dt) if dt is not None else "-"
    )
    # A data exibida também deve refletir o timezone destino (virada de dia)
    df["data_exibir"] = df["limite_dest"].apply(
        lambda dt: dt.strftime("%d/%m/%Y") if dt is not None else str(df.at[df.index[0], "data"])
    )

    colunas = {
        "nome": "Nome",
        "data_exibir": "Data",
        "horario_exibir": "Horário",
        "tipo": "Tipo",
    }
    df_exibir = df.rename(columns={"nome": "nome"})[list(colunas.keys())].rename(columns=colunas)

    return df_exibir, estado_linha


# ---------------------------------------------------------------------------
# View principal
# ---------------------------------------------------------------------------

def main():
    render_page_header(st, "Calendário da Temporada")

    # --- Seletor de Timezone ---
    labels_tz = [_offset_label(tz) for tz in TIMEZONES_OPCOES]
    label_default = _offset_label(TZ_ORIGEM)
    idx_default_tz = labels_tz.index(label_default) if label_default in labels_tz else 0

    label_selecionado = st.selectbox(
        "Timezone",
        labels_tz,
        index=idx_default_tz,
        key="calendario_timezone",
        help="Horários armazenados em America/Sao_Paulo. A conversão é apenas visual.",
    )
    # Recupera a string IANA correspondente ao label escolhido
    tz_selecionado = TIMEZONES_OPCOES[labels_tz.index(label_selecionado)]

    # --- Seletor de Temporada ---
    temporadas = get_season_options()
    temporada_atual = str(datetime.now().year)
    user_status = str(st.session_state.get("user_status", "")).strip().lower()
    if user_status and user_status != "ativo":
        if temporada_atual not in temporadas:
            temporadas = sorted(set([*temporadas, temporada_atual]))

    if not temporadas:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return

    entering_calendar_page = st.session_state.get("_previous_page") != st.session_state.get("_current_page")
    selected_temporada = st.session_state.get("calendario_temporada")

    if entering_calendar_page and temporada_atual in temporadas:
        st.session_state["calendario_temporada"] = temporada_atual
    elif selected_temporada not in temporadas:
        if temporada_atual in temporadas:
            st.session_state["calendario_temporada"] = temporada_atual
        else:
            default_index = get_default_season_index(temporadas)
            st.session_state["calendario_temporada"] = temporadas[default_index]

    temporada = st.selectbox("Temporada", temporadas, key="calendario_temporada")

    # --- Carrega provas ---
    provas_df = get_provas_df()
    if provas_df.empty:
        st.info("Nenhuma prova cadastrada.")
        return

    df = provas_df.copy()
    if "data" in df.columns:
        df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data_dt")
    if "horario_prova" not in df.columns:
        df["horario_prova"] = ""
    if "tipo" not in df.columns:
        df["tipo"] = "Normal"

    # now_aware: datetime atual no timezone selecionado (para comparações)
    now_aware = datetime.now(ZoneInfo(tz_selecionado))

    tab_calendario, tab_horario = st.tabs(["Calendário", "Horário limite"])

    # ----------------------------------------------------------------
    with tab_calendario:
        eventos = _build_calendar_events(df, tz_selecionado)
        hoje_iso = now_aware.date().isoformat()
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
        calendar(events=eventos, options=calendar_options, key=f"calendar_{temporada}_{tz_selecionado}")
        st.caption(
            f"Horários exibidos em **{tz_selecionado}**. "
            "Calendário inicia em Lista do mês atual; use a barra superior para trocar a visualização."
        )

    # ----------------------------------------------------------------
    with tab_horario:
        df_temp = df.copy()
        if "temporada" in df_temp.columns:
            df_temp = df_temp[
                df_temp["temporada"].astype(str).str.strip() == str(temporada).strip()
            ]

        if df_temp.empty:
            st.info("Nenhuma prova cadastrada para a temporada selecionada.")
            return

        df_exibir, estado_linha = _build_tabela_horario(df_temp, tz_selecionado, now_aware)

        def _style_linha(row: pd.Series) -> list[str]:
            estado = estado_linha.get(row.name, "normal")
            if estado == "passada":
                return ["color: #8B93A1; background-color: #F8FAFC;"] * len(row)
            if estado == "proxima":
                return ["background-color: #FFF7D6; color: #1F2937; font-weight: 700;"] * len(row)
            return [""] * len(row)

        styled_df = df_exibir.style.apply(_style_linha, axis=1)

        st.caption(
            f"Horários exibidos em **{tz_selecionado}**. "
            "Provas já encerradas aparecem esmaecidas e a próxima prova fica destacada."
        )
        st.dataframe(styled_df, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
