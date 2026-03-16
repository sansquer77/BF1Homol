import streamlit as st
import pandas as pd
import logging
from db.db_utils import db_connect
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options

logger = logging.getLogger(__name__)

def carregar_logs(temporada=None, usuario_id=None, is_admin=False):
    """Carrega logs de apostas, opcionalmente filtrando por temporada"""
    with db_connect() as conn:
        cols_info = pd.read_sql("PRAGMA table_info(log_apostas)", conn)
        has_status = "status" in cols_info["name"].values if not cols_info.empty else False
        has_ip_address = "ip_address" in cols_info["name"].values if not cols_info.empty else False
        has_usuario_id = "usuario_id" in cols_info["name"].values if not cols_info.empty else False
        status_expr = "status" if has_status else "'Registrada' AS status"
        ip_expr = "ip_address" if has_ip_address else "NULL AS ip_address"
        user_expr = "usuario_id" if has_usuario_id else "NULL AS usuario_id"

        where_clauses = []
        params = []

        if temporada:
            where_clauses.append("(temporada = ? OR temporada IS NULL)")
            params.append(temporada)

        if not is_admin:
            if not has_usuario_id or usuario_id is None:
                return pd.DataFrame()
            where_clauses.append("usuario_id = ?")
            params.append(int(usuario_id))

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        query = (
            f"SELECT id, {user_expr}, data, horario, apostador, nome_prova, pilotos, aposta, piloto_11, "
            f"tipo_aposta, automatica, {ip_expr}, temporada, {status_expr} "
            f"FROM log_apostas{where_sql} ORDER BY id DESC"
        )
        df = pd.read_sql(query, conn, params=tuple(params) if params else None)
    return df

def main():
    render_page_header(st, "Log de Apostas")

    perfil = st.session_state.get("user_role", "participante")
    is_admin = perfil in ("admin", "master")
    user_id = st.session_state.get("user_id")
    if not is_admin and not user_id:
        st.info("Sessão inválida ou expirada. Faça login novamente.")
        return

    # Season selector - read from temporadas table
    season_options = get_season_options(fallback_years=["2025", "2026"])
    if not season_options:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    default_index = get_default_season_index(season_options)
    
    season = st.selectbox("Temporada", season_options, index=default_index, key="log_apostas_season")
    st.session_state['temporada'] = season

    df = carregar_logs(season, usuario_id=user_id, is_admin=is_admin)
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
    filtro_show["Tipo de Aposta"] = filtro["tipo_aposta"].map(tipos_map)
    filtro_show["Automática"] = filtro["automatica"].apply(lambda x: "Sim" if x > 0 else "Não")
    if "pilotos" in filtro_show.columns:
        filtro_show["Pilotos/Fichas"] = filtro_show.apply(
            lambda r: f"{r.get('pilotos', '')} | {r.get('aposta', '')}".strip(" |"),
            axis=1
        )
    else:
        filtro_show["Pilotos/Fichas"] = filtro_show["aposta"]

    colunas_exibir = [
        "data", "horario", "apostador", "nome_prova", "Pilotos/Fichas", "piloto_11", "Tipo de Aposta", "Automática", "ip_address", "status"
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
                "status": "Status"
            }),
            width="stretch"
        )
    else:
        st.dataframe(filtro_show, width="stretch")

    st.caption("*O campo 'Automática' indica apostas geradas automaticamente pelo sistema (qualquer valor > 0 no campo).*")

if __name__ == "__main__":
    main()
