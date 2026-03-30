import datetime
import pandas as pd
import streamlit as st

from db.db_utils import db_connect
from utils.helpers import render_page_header


def _table_height(total_rows: int, row_height: int = 36, max_height: int = 620) -> int:
    return min(max_height, 42 + (max(total_rows, 1) * row_height))


def _load_access_logs(
    data_inicial: datetime.date,
    data_final: datetime.date,
    perfil_sel: str,
    evento_sel: str,
    sucesso_sel: str,
    ip_contains: str,
    usuario_contains: str,
) -> pd.DataFrame:
    where = ["DATE(created_at) >= ?", "DATE(created_at) <= ?"]
    params: list[object] = [data_inicial.isoformat(), data_final.isoformat()]

    if perfil_sel != "Todos":
        where.append("LOWER(COALESCE(perfil, '')) = ?")
        params.append(perfil_sel.lower())

    if evento_sel != "Todos":
        where.append("evento = ?")
        params.append(evento_sel)

    if sucesso_sel == "Sucesso":
        where.append("sucesso = ?")
        params.append(True)
    elif sucesso_sel == "Falha":
        where.append("sucesso = ?")
        params.append(False)

    if ip_contains:
        where.append("LOWER(COALESCE(ip_address, '')) LIKE ?")
        params.append(f"%{ip_contains.lower()}%")

    if usuario_contains:
        where.append("(LOWER(COALESCE(email, '')) LIKE ? OR LOWER(COALESCE(nome, '')) LIKE ?)")
        token = f"%{usuario_contains.lower()}%"
        params.extend([token, token])

    where_sql = " AND ".join(where)

    query = f"""
        SELECT
            id,
            created_at,
            evento,
            sucesso,
            user_id,
            email,
            nome,
            perfil,
            ip_address,
            detalhes
        FROM access_logs
        WHERE {where_sql}
        ORDER BY created_at DESC, id DESC
    """

    with db_connect() as conn:
        return pd.read_sql_query(query, conn, params=tuple(params))


def _get_filter_options() -> tuple[list[str], list[str]]:
    with db_connect() as conn:
        perfis_df = pd.read_sql_query(
            """
            SELECT DISTINCT LOWER(TRIM(COALESCE(perfil, ''))) AS perfil
            FROM access_logs
            WHERE perfil IS NOT NULL AND TRIM(COALESCE(perfil, '')) <> ''
            ORDER BY perfil
            """,
            conn,
        )
        eventos_df = pd.read_sql_query(
            """
            SELECT DISTINCT evento
            FROM access_logs
            WHERE evento IS NOT NULL AND TRIM(COALESCE(evento, '')) <> ''
            ORDER BY evento
            """,
            conn,
        )

    perfis_series = perfis_df["perfil"] if "perfil" in perfis_df.columns else pd.Series(dtype="string")
    eventos_series = eventos_df["evento"] if "evento" in eventos_df.columns else pd.Series(dtype="string")

    perfis: list[str] = [str(p).strip() for p in perfis_series.fillna("").tolist() if str(p).strip()]
    eventos: list[str] = [str(e).strip() for e in eventos_series.fillna("").tolist() if str(e).strip()]
    return perfis, eventos


def main() -> None:
    render_page_header(st, "Log de Acessos")

    perfil = str(st.session_state.get("user_role", "")).strip().lower()
    if perfil != "master":
        st.error("Acesso negado: somente Master pode visualizar o log de acessos.")
        return

    data_final_default = datetime.date.today()
    data_inicial_default = data_final_default - datetime.timedelta(days=7)

    col_data_i, col_data_f, col_status = st.columns([1, 1, 1])
    with col_data_i:
        data_inicial = st.date_input("Data inicial", value=data_inicial_default)
    with col_data_f:
        data_final = st.date_input("Data final", value=data_final_default)
    with col_status:
        sucesso_sel = st.selectbox("Resultado", ["Todos", "Sucesso", "Falha"], index=0)

    if data_inicial > data_final:
        st.warning("A data inicial não pode ser maior que a data final.")
        return

    perfis, eventos = _get_filter_options()

    col_perfil, col_evento, col_ip, col_usuario = st.columns([1, 1, 1, 1])
    with col_perfil:
        perfil_sel = st.selectbox("Perfil", ["Todos"] + perfis, index=0)
    with col_evento:
        evento_sel = st.selectbox("Evento", ["Todos"] + eventos, index=0)
    with col_ip:
        ip_contains = st.text_input("IP contém", value="").strip()
    with col_usuario:
        usuario_contains = st.text_input("Usuário/Email contém", value="").strip()

    df = _load_access_logs(
        data_inicial=data_inicial,
        data_final=data_final,
        perfil_sel=perfil_sel,
        evento_sel=evento_sel,
        sucesso_sel=sucesso_sel,
        ip_contains=ip_contains,
        usuario_contains=usuario_contains,
    )

    if df.empty:
        st.info("Nenhum acesso encontrado com os filtros selecionados.")
        return

    total = len(df)
    total_sucesso = int((df["sucesso"] == 1).sum())
    total_falha = total - total_sucesso

    m1, m2, m3 = st.columns(3)
    m1.metric("Total de eventos", total)
    m2.metric("Sucessos", total_sucesso)
    m3.metric("Falhas", total_falha)

    df_show = df.copy()
    df_show["sucesso"] = df_show["sucesso"].apply(lambda x: "Sucesso" if bool(x) else "Falha")

    st.dataframe(
        df_show.rename(
            columns={
                "created_at": "Data/Hora",
                "evento": "Evento",
                "sucesso": "Resultado",
                "user_id": "User ID",
                "email": "Email",
                "nome": "Nome",
                "perfil": "Perfil",
                "ip_address": "IP Origem",
                "detalhes": "Detalhes",
            }
        ),
        hide_index=True,
        height=_table_height(total),
    )


if __name__ == "__main__":
    main()
