import streamlit as st
import pandas as pd
import logging
from db.db_utils import db_connect
from db.db_utils import get_table_columns
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options

logger = logging.getLogger(__name__)


def _table_height(total_rows: int, row_height: int = 36, max_height: int = 620) -> int:
    return min(max_height, 42 + (max(total_rows, 1) * row_height))


def _formatar_horario_hhmmss(valor: object) -> str:
    """Normaliza diferentes representações de horário para HH:MM:SS."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""

    txt = str(valor).strip()
    if not txt:
        return ""
    if len(txt) == 8 and txt.count(":") == 2:
        return txt

    dt = pd.to_datetime(txt, errors="coerce")
    if not pd.isna(dt):
        return dt.strftime("%H:%M:%S")

    try:
        num = float(txt)
    except Exception:
        return txt

    abs_num = abs(num)
    if abs_num >= 1e18:
        unit = "ns"
    elif abs_num >= 1e15:
        unit = "us"
    elif abs_num >= 1e12:
        unit = "ms"
    else:
        unit = "s"

    dt_num = pd.to_datetime(num, unit=unit, errors="coerce")
    if pd.isna(dt_num):
        return txt
    return dt_num.strftime("%H:%M:%S")


def _to_int_safe(value: object) -> int:
    """Converte valor para int sem lançar exceção (retorna 0 em caso de falha)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def carregar_logs(temporada=None, usuario_id=None, usuario_nome=None, is_admin=False):
    """Carrega logs de apostas, opcionalmente filtrando por temporada."""
    with db_connect() as conn:
        cols = [str(c) for c in get_table_columns(conn, "log_apostas")]
        has_status = "status" in cols
        has_ip_address = "ip_address" in cols
        has_usuario_id = "usuario_id" in cols
        has_user_id = "user_id" in cols
        has_temporada = "temporada" in cols
        has_data = "data" in cols
        has_data_criacao = "data_criacao" in cols
        user_col = "usuario_id" if has_usuario_id else ("user_id" if has_user_id else None)
        status_expr = "status" if has_status else "'Registrada'"
        ip_expr = "ip_address" if has_ip_address else "NULL"
        user_expr = user_col if user_col else "NULL"

        where_clauses: list[str] = []
        params: list[object] = []

        if temporada:
            season_sources = []
            if has_temporada:
                season_sources.append("NULLIF(TRIM(CAST(temporada AS TEXT)), '')")
            if has_data:
                season_sources.append("NULLIF(SUBSTR(CAST(data AS TEXT), 1, 4), '')")
            if has_data_criacao:
                season_sources.append("NULLIF(SUBSTR(CAST(data_criacao AS TEXT), 1, 4), '')")

            if season_sources:
                season_expr = f"COALESCE({', '.join(season_sources)})"
                where_clauses.append(f"{season_expr} = %s")
                params.append(str(temporada).strip())

        if not is_admin:
            if not user_col or usuario_id is None:
                return pd.DataFrame()
            where_clauses.append(f"{user_col} = %s")
            params.append(int(usuario_id))

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = (
            "SELECT id, "
            f"{user_expr} AS usuario_id, "
            "data, horario, apostador, nome_prova, pilotos, aposta, piloto_11, "
            "tipo_aposta, automatica, "
            f"{ip_expr} AS ip_address, "
            "temporada, "
            f"{status_expr} AS status "
            f"FROM log_apostas{where_sql} ORDER BY id DESC"
        )

        # Usa cursor manual — pd.read_sql é incompatível com psycopg3 (dict_row)
        cur = conn.cursor()
        cur.execute(query, tuple(params) if params else ())
        rows = cur.fetchall() or []

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])

    # Garante tipos numéricos para colunas usadas em comparações
    for col in ("automatica", "tipo_aposta"):
        if col in df.columns:
            df[col] = df[col].apply(_to_int_safe)

    return df


def main():
    render_page_header(st, "Log de Apostas")

    perfil = st.session_state.get("user_role", "participante")
    is_admin = perfil in ("admin", "master")
    user_id = st.session_state.get("user_id")
    user_nome = st.session_state.get("user_nome")
    if not is_admin and not user_id:
        st.info("Sessão inválida ou expirada. Faça login novamente.")
        return

    season_options = get_season_options(fallback_years=["2025", "2026"])
    if not season_options:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    default_index = get_default_season_index(season_options)
    season = st.selectbox("Temporada", season_options, index=default_index, key="log_apostas_season")
    st.session_state["temporada"] = season

    df = carregar_logs(season, usuario_id=user_id, usuario_nome=user_nome, is_admin=is_admin)
    if df.empty:
        st.warning("Nenhum registro no log de apostas.")
        return

    tipos_map = {0: "Dentro do Prazo", 1: "Fora do Prazo"}

    st.markdown("### Filtros")
    colunas_filtro = []
    if perfil in ("admin", "master"):
        colunas_filtro.append("apostador")
    cols = st.columns(4)
    idx_filtro = 0

    if "apostador" in colunas_filtro:
        apostador_opcoes = ["Todos"] + sorted(df["apostador"].unique())
        apostador_sel = cols[idx_filtro].selectbox("Apostador", apostador_opcoes)
        idx_filtro += 1
    else:
        apostador_sel = "Todos"

    tipo_filtro = cols[idx_filtro].selectbox(
        "Tipo de Aposta", ["Todas"] + list(tipos_map.values())
    )
    idx_filtro += 1
    data_sel = cols[idx_filtro].selectbox(
        "Data", ["Todas"] + sorted(df["data"].unique(), reverse=True)
    )
    idx_filtro += 1

    status_sel = cols[idx_filtro].selectbox(
        "Status", ["Todos"] + sorted(df["status"].fillna("Registrada").unique().tolist())
    )

    mostrar_automaticas = st.checkbox("Mostrar apenas apostas automáticas (automatica > 0)", value=False)

    filtro = df.copy()

    if is_admin:
        if apostador_sel != "Todos":
            filtro = filtro[filtro["apostador"] == apostador_sel]

    if tipo_filtro != "Todas":
        inv_tipos_map = {v: k for k, v in tipos_map.items()}
        # tipo_aposta já é int graças à conversão em carregar_logs
        filtro = filtro[filtro["tipo_aposta"] == inv_tipos_map[tipo_filtro]]
    if data_sel != "Todas":
        filtro = filtro[filtro["data"] == data_sel]
    if status_sel != "Todos":
        filtro = filtro[filtro["status"].fillna("Registrada") == status_sel]
    if mostrar_automaticas:
        filtro = filtro[filtro["automatica"] > 0]

    if filtro.empty:
        st.info("Nenhum registro encontrado com os filtros selecionados.")
        return

    filtro_show = filtro.copy()
    if "horario" in filtro_show.columns:
        filtro_show["horario"] = filtro_show["horario"].apply(_formatar_horario_hhmmss)

    filtro_show["Tipo de Aposta"] = filtro["tipo_aposta"].map(tipos_map)
    filtro_show["Automática"] = filtro["automatica"].apply(lambda x: "Sim" if x > 0 else "Não")
    if "pilotos" in filtro_show.columns:
        pilotos_str = filtro_show["pilotos"].fillna("").astype(str).str.strip()
        aposta_str = filtro_show["aposta"].fillna("").astype(str).str.strip()
        filtro_show["Pilotos/Fichas"] = (pilotos_str + " | " + aposta_str).str.strip(" |")
    else:
        filtro_show["Pilotos/Fichas"] = filtro_show["aposta"]

    colunas_exibir = [
        "data", "horario", "apostador", "nome_prova", "Pilotos/Fichas",
        "piloto_11", "Tipo de Aposta", "Automática", "ip_address", "status",
    ]
    if "automatica" in filtro_show.columns and "tipo_aposta" in filtro_show.columns:
        st.dataframe(
            filtro_show[colunas_exibir].rename(columns={
                "data": "Data",
                "horario": "Horário",
                "apostador": "Apostador",
                "nome_prova": "Prova",
                "Pilotos/Fichas": "Pilotos/Fichas",
                "piloto_11": "11º Colocado",
                "ip_address": "IP",
                "status": "Status",
            }),
            width="stretch",
            hide_index=True,
            height=_table_height(len(filtro_show)),
            column_config={
                "Data": st.column_config.TextColumn("Data", width="small"),
                "Horário": st.column_config.TextColumn("Horário", width="small"),
                "Apostador": st.column_config.TextColumn("Apostador", width="medium"),
                "Prova": st.column_config.TextColumn("Prova", width="large"),
                "Pilotos/Fichas": st.column_config.TextColumn("Pilotos/Fichas", width="large"),
                "11º Colocado": st.column_config.TextColumn("11º Colocado", width="medium"),
                "Tipo de Aposta": st.column_config.TextColumn("Tipo de Aposta", width="medium"),
                "Automática": st.column_config.TextColumn("Automática", width="small"),
                "IP": st.column_config.TextColumn("IP", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            },
        )
    else:
        st.dataframe(filtro_show, width="stretch", hide_index=True, height=_table_height(len(filtro_show)))

    st.caption("*O campo 'Automática' indica apostas geradas automaticamente pelo sistema (qualquer valor > 0 no campo).*")


if __name__ == "__main__":
    main()
