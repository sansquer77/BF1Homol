import streamlit as st
import pandas as pd
import logging
from dataclasses import dataclass
from services.data_access_core import db_connect, get_table_columns
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options
from utils.timezone_utils import convert_utc_to_client_tz
from utils.pagination import paginate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BettingLogResult:
    rows: pd.DataFrame
    total: int


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


def _sorted_unique_non_null(series: pd.Series, reverse: bool = False) -> list[object]:
    """Retorna valores únicos não nulos com ordenação robusta para tipos mistos."""
    values = [v for v in series.dropna().tolist() if not pd.isna(v)]
    if not values:
        return []
    try:
        return sorted(set(values), reverse=reverse)
    except TypeError:
        # Fallback para cenários com mistura de tipos (ex.: str + None já filtrado)
        return sorted({str(v) for v in values}, reverse=reverse)


def _normalize_date_for_filter(value: object) -> str:
    """Normaliza valor de data para yyyy-mm-dd para uso em filtros."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""

    txt = str(value).strip()
    if not txt:
        return ""

    dt = pd.to_datetime(txt, errors="coerce")
    if pd.isna(dt):
        return txt
    return dt.strftime("%Y-%m-%d")


def carregar_logs(
    temporada=None,
    usuario_id=None,
    usuario_nome=None,
    is_admin=False,
    *,
    apostador=None,
    tipo_aposta=None,
    data=None,
    status=None,
    apenas_automaticas=False,
    limit=100,
    offset=0,
) -> BettingLogResult:
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
                return BettingLogResult(pd.DataFrame(), 0)
            where_clauses.append(f"{user_col} = %s")
            params.append(int(usuario_id))

        if is_admin and apostador:
            where_clauses.append("LOWER(COALESCE(apostador, '')) LIKE %s")
            params.append(f"%{str(apostador).strip().lower()}%")
        if tipo_aposta is not None:
            where_clauses.append("tipo_aposta = %s")
            params.append(int(tipo_aposta))
        if data:
            where_clauses.append("SUBSTR(CAST(data AS TEXT), 1, 10) = %s")
            params.append(str(data).strip())
        if status:
            where_clauses.append(f"{status_expr} = %s")
            params.append(str(status).strip())
        if apenas_automaticas:
            where_clauses.append("COALESCE(automatica, 0) > 0")

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = (
            "SELECT id, "
            f"{user_expr} AS usuario_id, "
            "data, horario, apostador, nome_prova, pilotos, aposta, piloto_11, "
            "tipo_aposta, automatica, "
            f"{ip_expr} AS ip_address, "
            "temporada, "
            f"{status_expr} AS status "
            f"FROM log_apostas{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s"
        )
        page_params = [*params, max(1, min(int(limit), 500)), max(0, int(offset))]

        # Usa cursor manual — pd.read_sql é incompatível com psycopg3 (dict_row)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS total FROM log_apostas{where_sql}", tuple(params))
        count_row = cur.fetchone() or {}
        cur.execute(query, tuple(page_params))
        rows = cur.fetchall() or []

    if not rows:
        return BettingLogResult(pd.DataFrame(), int(count_row.get("total") or 0))

    df = pd.DataFrame([dict(r) for r in rows])

    # Garante tipos numéricos para colunas usadas em comparações
    for col in ("automatica", "tipo_aposta"):
        if col in df.columns:
            df[col] = df[col].apply(_to_int_safe)

    return BettingLogResult(df, int(count_row.get("total") or 0))


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

    tipos_map = {0: "Dentro do Prazo", 1: "Fora do Prazo"}

    st.markdown("### Filtros")
    with st.expander("Abrir filtros", expanded=False):
        row1_col1, row1_col2 = st.columns(2)
        row2_col1, row2_col2 = st.columns(2)

        if is_admin:
            apostador_sel = row1_col1.text_input("Apostador contém").strip()
        else:
            apostador_sel = ""

        tipo_filtro = row1_col2.selectbox(
            "Tipo de Aposta", ["Todas"] + list(tipos_map.values())
        )
        data_sel = row2_col1.text_input("Data exata (AAAA-MM-DD)").strip()
        status_sel = row2_col2.text_input("Status exato").strip()

        mostrar_automaticas = st.checkbox(
            "Mostrar apenas apostas automáticas (automatica > 0)",
            value=False,
        )

    inv_tipos_map = {v: k for k, v in tipos_map.items()}
    tipo_value = None if tipo_filtro == "Todas" else inv_tipos_map[tipo_filtro]
    filter_signature = (
        season, apostador_sel, tipo_value, data_sel, status_sel,
        mostrar_automaticas, user_id, is_admin,
    )
    if st.session_state.get("_log_apostas_filter_signature") != filter_signature:
        st.session_state["_log_apostas_filter_signature"] = filter_signature
        st.session_state["log_apostas_page"] = 1

    page_size = st.selectbox("Registros por página", [50, 100, 200], index=1, key="log_apostas_page_size")
    requested_page = int(st.session_state.get("log_apostas_page", 1))
    query_args = dict(
        temporada=season, usuario_id=user_id, usuario_nome=user_nome, is_admin=is_admin,
        apostador=apostador_sel, tipo_aposta=tipo_value, data=data_sel,
        status=status_sel, apenas_automaticas=mostrar_automaticas,
        limit=page_size, offset=(requested_page - 1) * page_size,
    )
    result = carregar_logs(**query_args)
    pagination = paginate(requested_page, page_size, result.total)
    if pagination.page != requested_page:
        query_args["offset"] = pagination.offset
        result = carregar_logs(**query_args)
        st.session_state["log_apostas_page"] = pagination.page
    filtro = result.rows

    if filtro.empty:
        st.info("Nenhum registro encontrado com os filtros selecionados.")
        return

    nav_prev, nav_text, nav_next = st.columns([1, 2, 1])
    if nav_prev.button("← Anterior", disabled=pagination.page <= 1, key="log_apostas_prev"):
        st.session_state["log_apostas_page"] = pagination.page - 1
        st.rerun()
    nav_text.caption(
        f"Página {pagination.page} de {pagination.total_pages} · "
        f"{result.total} registros encontrados"
    )
    if nav_next.button(
        "Próxima →",
        disabled=pagination.page >= pagination.total_pages,
        key="log_apostas_next",
    ):
        st.session_state["log_apostas_page"] = pagination.page + 1
        st.rerun()

    filtro_show = filtro.copy()
    
    # Preparação de dados para exibição
    client_tz = st.session_state.get("client_timezone", "UTC")
    
    # 'horario' é TIMESTAMP - converte para timezone do cliente (formato completo)
    if "horario" in filtro_show.columns:
        filtro_show["horario"] = filtro_show["horario"].apply(
            lambda x: convert_utc_to_client_tz(x, client_tz, "%d/%m/%Y %H:%M:%S") if pd.notna(x) else ""
        )
    
    # 'data' é apenas a data em string (YYYY-MM-DD) - apenas normaliza para DD/MM/YYYY
    if "data" in filtro_show.columns:
        def formatar_data(valor):
            if valor is None or (isinstance(valor, float) and pd.isna(valor)):
                return ""
            txt = str(valor).strip()
            if not txt:
                return ""
            try:
                # Se for YYYY-MM-DD, converte para DD/MM/YYYY
                dt = pd.to_datetime(txt, format="%Y-%m-%d", errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%d/%m/%Y")
            except Exception:
                pass
            return txt
        
        filtro_show["data"] = filtro_show["data"].apply(formatar_data)

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
