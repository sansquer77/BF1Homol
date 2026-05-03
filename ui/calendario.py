"""Módulo de Calendário da Temporada.

Regras de timezone:
    - O banco de dados armazena todos os horários em America/Sao_Paulo (sem
      conversão automática pelo driver). Os valores lidos são, portanto,
      "naive" mas implícita e canonicamente SÃO PAULO.
    - O timezone de exibição é lido de st.session_state["client_timezone"],
      que é gerenciado exclusivamente pelo seletor da sidebar em main.py.
    - Nenhum dado é alterado no banco; a conversão é apenas visual.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from streamlit_calendar import calendar
from services.data_access_provas import get_provas_df
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Timezone canônico do banco de dados.
_TZ_BD = "America/Sao_Paulo"
# Fallback caso client_timezone não esteja definido na sessão.
_TZ_DEFAULT = _TZ_BD


# ---------------------------------------------------------------------------
# Helpers de timezone
# ---------------------------------------------------------------------------

def _get_tz_exibicao() -> str:
    """Retorna o timezone de exibição configurado pelo usuário na sidebar.

    Lido de st.session_state["client_timezone"], gerenciado por main.py.
    Retorna o timezone padrão (America/Sao_Paulo) como fallback seguro.
    """
    tz = st.session_state.get("client_timezone", _TZ_DEFAULT)
    try:
        ZoneInfo(tz)  # valida
        return tz
    except Exception:
        return _TZ_DEFAULT


def _localizar_e_converter(dt_naive: datetime, tz_destino: str) -> datetime:
    """Atribui o fuso do BD (São Paulo) ao datetime naive e converte para destino.

    Args:
        dt_naive: datetime sem tzinfo lido do banco (implicitamente SP).
        tz_destino: string IANA do timezone de destino.

    Returns:
        datetime aware no timezone de destino.
    """
    dt_sp = dt_naive.replace(tzinfo=ZoneInfo(_TZ_BD))
    return dt_sp.astimezone(ZoneInfo(tz_destino))


def _formatar_horario(dt_aware: datetime) -> str:
    """Formata datetime aware para 'HH:MM'."""
    return dt_aware.strftime("%H:%M")


# ---------------------------------------------------------------------------
# Helpers de parsing de dados brutos
# ---------------------------------------------------------------------------

def _parse_horario(value: object) -> tuple[int, int] | None:
    """Converte valores de horario_prova para (hora, minuto)."""
    if value is None:
        return None
    raw = str(value).strip().replace("h", ":")
    if not raw or ":" not in raw:
        return None
    hh, mm, *_ = raw.split(":")
    if not hh.isdigit() or not mm.isdigit():
        return None
    hour, minute = int(hh), int(mm)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def _build_dt_sp(data_dt: pd.Timestamp, horario_value: object) -> datetime | None:
    """Constrói datetime aware em America/Sao_Paulo a partir dos campos brutos.

    Args:
        data_dt: Timestamp da data da prova (naive, representa SP).
        horario_value: Valor bruto de horario_prova.

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
        # Sem horário: limite conservador no fim do dia.
        dt_naive = data_dt.to_pydatetime().replace(hour=23, minute=59, second=59, microsecond=0)
    return dt_naive.replace(tzinfo=ZoneInfo(_TZ_BD))


# ---------------------------------------------------------------------------
# Construtores de dados para as abas
# ---------------------------------------------------------------------------

def _build_calendar_events(df: pd.DataFrame, tz_destino: str) -> list[dict]:
    """Gera lista de eventos para o componente streamlit-calendar.

    Os horários são convertidos do BD (SP) para o timezone de exibição
    antes de serializar como ISO strings com offset.

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

    Converte os horários do BD (SP) para o timezone de exibição e classifica
    cada linha como 'passada', 'proxima' ou 'normal' para o estilo visual.

    Args:
        df_temporada: Provas já filtradas pela temporada selecionada.
        tz_destino: Timezone de exibição selecionado pelo usuário.
        now_aware: Datetime atual com tzinfo (para comparar com o limite).

    Returns:
        Tupla (DataFrame formatado para exibir, dict {index: estado}).
    """
    df = df_temporada.copy()

    # Monta datetime aware (SP) e converte para o destino.
    df["limite_sp"] = df.apply(
        lambda row: _build_dt_sp(row.get("data_dt"), row.get("horario_prova")), axis=1
    )
    df["limite_dest"] = df["limite_sp"].apply(
        lambda dt: dt.astimezone(ZoneInfo(tz_destino)) if dt is not None else None
    )

    # Determina próxima prova.
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

    # Formata colunas de exibição no timezone destino.
    df["horario_exibir"] = df["limite_dest"].apply(
        lambda dt: _formatar_horario(dt) if dt is not None else "-"
    )
    # A data também pode mudar (ex.: virada de dia em fusos adiantados).
    df["data_exibir"] = df["limite_dest"].apply(
        lambda dt: dt.strftime("%d/%m/%Y") if dt is not None else "-"
    )

    colunas_exibir = {
        "nome": "Nome",
        "data_exibir": "Data",
        "horario_exibir": "Horário",
        "tipo": "Tipo",
    }
    df_exibir = df.rename(columns=colunas_exibir)[list(colunas_exibir.values())]

    return df_exibir, estado_linha


# ---------------------------------------------------------------------------
# View principal
# ---------------------------------------------------------------------------

def main():
    render_page_header(st, "Calendário da Temporada")

    # Timezone de exibição gerenciado pela sidebar (main.py).
    tz_exibicao = _get_tz_exibicao()
    now_aware = datetime.now(ZoneInfo(tz_exibicao))

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

    # --- Carrega e prepara provas ---
    provas_df = get_provas_df(temporada=temporada)
    if provas_df.empty:
        st.info("Nenhuma prova cadastrada para a temporada selecionada.")
        return

    df = provas_df.copy()
    if "data" in df.columns:
        df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data_dt")
    if "horario_prova" not in df.columns:
        df["horario_prova"] = ""
    if "tipo" not in df.columns:
        df["tipo"] = "Normal"

    tab_calendario, tab_horario = st.tabs(["Calendário", "Horário limite"])

    # ----------------------------------------------------------------
    with tab_calendario:
        # Debug: mostrar timezone sendo usado
        st.write(f"🔍 **Debug** - Timezone em uso: `{tz_exibicao}` | Temporada: `{temporada}`")
        
        eventos = _build_calendar_events(df, tz_exibicao)
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
        # A key inclui o TZ para forçar re-render quando o usuário muda o fuso.
        calendar(events=eventos, options=calendar_options, key=f"calendar_{temporada}_{tz_exibicao}")
        st.caption(
            f"Horários exibidos em **{tz_exibicao}**. "
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

        df_exibir, estado_linha = _build_tabela_horario(df_temp, tz_exibicao, now_aware)

        def _style_linha(row: pd.Series) -> list[str]:
            estado = estado_linha.get(row.name, "normal")
            if estado == "passada":
                return ["color: #8B93A1; background-color: #F8FAFC;"] * len(row)
            if estado == "proxima":
                return ["background-color: #FFF7D6; color: #1F2937; font-weight: 700;"] * len(row)
            return [""] * len(row)

        styled_df = df_exibir.style.apply(_style_linha, axis=1)

        st.caption(
            f"Horários exibidos em **{tz_exibicao}**. "
            "Provas já encerradas aparecem esmaecidas e a próxima prova fica destacada."
        )
        st.dataframe(styled_df, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
