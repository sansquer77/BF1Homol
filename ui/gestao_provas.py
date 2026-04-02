"""
Gestão de Provas - BF1 3.0
Corrigido com context manager para pool de conexões
Reorganizado em abas: Editar Provas / Adicionar Nova Prova
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from db.db_schema import db_connect, get_table_columns
from db.repo_races import get_provas_df
from db.circuitos_utils import atualizar_base_circuitos, get_circuitos_df, get_temporadas_existentes_provas
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def _normalizar_df_provas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza DataFrame de provas para evitar quebra por IDs inválidos."""
    if df.empty:
        return df

    df_norm = df.copy()
    if "id" not in df_norm.columns:
        return pd.DataFrame(columns=df_norm.columns)

    df_norm["id"] = pd.to_numeric(df_norm["id"], errors="coerce")
    df_norm = df_norm[df_norm["id"].notna()].copy()
    df_norm["id"] = df_norm["id"].astype(int)
    return df_norm


def _on_prova_change():
    """Callback para limpar os valores do formulário quando a prova selecionada mudar."""
    # Limpar os valores armazenados para forçar atualização do formulário
    keys_to_clear = [
        "edit_nome_prova_val", "edit_data_prova_val", "edit_horario_prova_val",
        "edit_status_prova_val", "edit_tipo_prova_val", "edit_temporada_prova_val"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def _render_tabela_provas(df: pd.DataFrame):
    """Renderiza a tabela de provas cadastradas."""
    if df.empty:
        st.info("Nenhuma prova cadastrada.")
        return
    
    st.markdown("### 📋 Provas Cadastradas")
    cols_display = ["id", "nome", "data", "status"]
    col_names = ["ID", "Nome", "Data", "Status"]
    
    # Adicionar coluna Tipo
    if "tipo" in df.columns:
        cols_display.append("tipo")
        col_names.append("Tipo")
    
    # Adicionar coluna Temporada
    if "temporada" in df.columns:
        cols_display.append("temporada")
        col_names.append("Temporada")

    if "circuit_id" in df.columns:
        cols_display.append("circuit_id")
        col_names.append("Circuit ID")
    
    show_df = df[cols_display].copy()
    show_df.columns = col_names
    st.dataframe(show_df, width="stretch")


def _render_aba_editar(df: pd.DataFrame):
    """Renderiza a aba de edição de provas existentes."""
    # Tabela de provas
    _render_tabela_provas(df)
    
    st.markdown("---")
    st.markdown("### ✏️ Editar Prova Selecionada")
    
    if df.empty:
        st.warning("Não há provas para editar. Adicione uma prova na aba 'Adicionar Nova Prova'.")
        return
    
    # Criar lista de opções com ID para evitar ambiguidade
    df["opcao_display"] = df.apply(
        lambda r: f"{r['nome']} ({r['data']}) - ID: {r['id']}", axis=1
    )
    opcoes = df["opcao_display"].tolist()
    
    # Selectbox com callback para atualizar formulário
    selected = st.selectbox(
        "Selecione uma prova para editar",
        opcoes,
        key="sel_prova_edit",
        on_change=_on_prova_change
    )
    
    # Encontrar a prova selecionada
    prova_row = df[df["opcao_display"] == selected].iloc[0]
    try:
        prova_id = int(prova_row["id"])
    except (TypeError, ValueError):
        st.error("❌ ID da prova inválido. Atualize a página e tente novamente.")
        return
    
    # Obter valores da prova selecionada
    nome_atual = prova_row["nome"]
    data_atual = pd.to_datetime(prova_row["data"]).date()
    
    horario_atual = prova_row.get("horario_prova", "14:00:00")
    try:
        horario_time = pd.to_datetime(str(horario_atual), format="%H:%M:%S").time()
    except Exception:
        horario_time = pd.to_datetime("14:00:00", format="%H:%M:%S").time()
    
    status_atual = prova_row.get("status", "Ativa")
    tipo_atual = prova_row.get("tipo", "Normal")
    
    current_year = str(datetime.now().year)
    temporada_atual = str(prova_row.get("temporada", current_year))
    temporadas = get_season_options(ensure_values=[temporada_atual])
    
    # Formulário de edição - usar key única baseada no ID da prova
    novo_nome = st.text_input(
        "Nome da prova",
        value=nome_atual,
        key=f"edit_nome_prova_{prova_id}"
    )
    
    nova_data = st.date_input(
        "Data da prova",
        value=data_atual,
        key=f"edit_data_prova_{prova_id}"
    )
    
    novo_horario = st.time_input(
        "Horário da prova (Fuso Horário: São Paulo/Brasil - Bloqueio de apostas após este horário)",
        value=horario_time,
        key=f"edit_horario_prova_{prova_id}",
        help="Horário em formato 24h (ex: 14:00 para 2 PM). Apostas serão bloqueadas após este horário em qualquer fuso horário."
    )
    
    status_options = ["Ativa", "Inativa"]
    try:
        status_index = status_options.index(status_atual)
    except ValueError:
        status_index = 0
    novo_status = st.selectbox(
        "Status",
        status_options,
        index=status_index,
        key=f"edit_status_prova_{prova_id}"
    )
    
    tipo_options = ["Normal", "Sprint"]
    tipo_index = tipo_options.index(tipo_atual) if tipo_atual in tipo_options else 0
    novo_tipo = st.selectbox(
        "Tipo",
        tipo_options,
        index=tipo_index,
        key=f"edit_tipo_prova_{prova_id}"
    )
    
    temporada_index = temporadas.index(temporada_atual) if temporada_atual in temporadas else 0
    nova_temporada = st.selectbox(
        "Temporada",
        temporadas,
        index=temporada_index,
        key=f"edit_temporada_prova_{prova_id}"
    )

    # Vinculo opcional do circuito Ergast/Jolpica
    try:
        circuitos_df = get_circuitos_df()
    except Exception:
        circuitos_df = pd.DataFrame()
    circuito_atual = str(prova_row.get("circuit_id", "") or "").strip()
    opcoes_circuito = ["(Sem vínculo)"]
    mapa_circuito = {"(Sem vínculo)": None}
    if not circuitos_df.empty:
        for _, r in circuitos_df.iterrows():
            cid = str(r.get("circuit_id", "")).strip()
            if not cid:
                continue
            cname = str(r.get("circuit_name", cid)).strip()
            country = str(r.get("country", "")).strip()
            locality = str(r.get("locality", "")).strip()
            geo = ", ".join([x for x in [locality, country] if x])
            label = f"{cname} ({geo}) - {cid}" if geo else f"{cname} - {cid}"
            opcoes_circuito.append(label)
            mapa_circuito[label] = cid
    valor_circuito = "(Sem vínculo)"
    for label, cid in mapa_circuito.items():
        if cid and cid == circuito_atual:
            valor_circuito = label
            break
    novo_circuito_label = st.selectbox(
        "Circuito (base Ergast/Jolpica)",
        opcoes_circuito,
        index=opcoes_circuito.index(valor_circuito),
        key=f"edit_circuito_prova_{prova_id}",
    )
    novo_circuito_id = mapa_circuito.get(novo_circuito_label)
    
    col1, col2 = st.columns(2)
    
    # Botão: Atualizar
    with col1:
        if st.button("🔄 Atualizar prova", key="btn_update_prova", type="primary"):
            horario_str = novo_horario.strftime("%H:%M:%S")
            with db_connect() as conn:
                c = conn.cursor()
                cols = get_table_columns(conn, 'provas')
                if "temporada" in cols and "circuit_id" in cols:
                    c.execute(
                        "UPDATE provas SET nome=%s, data=%s, horario_prova=%s, status=%s, tipo=%s, temporada=%s, circuit_id=%s WHERE id=%s",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, nova_temporada, novo_circuito_id, prova_id)
                    )
                elif "temporada" in cols:
                    c.execute(
                        "UPDATE provas SET nome=%s, data=%s, horario_prova=%s, status=%s, tipo=%s, temporada=%s WHERE id=%s",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, nova_temporada, prova_id)
                    )
                elif "circuit_id" in cols:
                    c.execute(
                        "UPDATE provas SET nome=%s, data=%s, horario_prova=%s, status=%s, tipo=%s, circuit_id=%s WHERE id=%s",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, novo_circuito_id, prova_id)
                    )
                else:
                    c.execute(
                        "UPDATE provas SET nome=%s, data=%s, horario_prova=%s, status=%s, tipo=%s WHERE id=%s",
                        (novo_nome, nova_data.strftime('%Y-%m-%d'), horario_str, novo_status, novo_tipo, prova_id)
                    )
                conn.commit()
            
            st.success("✅ Prova atualizada com sucesso!")
            st.cache_data.clear()
            st.rerun()
    
    # Botão: Excluir
    with col2:
        if st.button("🗑️ Excluir prova", key="btn_delete_prova"):
            with db_connect() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM provas WHERE id=%s", (prova_id,))
                conn.commit()
            
            st.success("✅ Prova exluída com sucesso!")
            st.cache_data.clear()
            st.rerun()


def _render_aba_adicionar():
    """Renderiza a aba de adicionar nova prova."""
    st.markdown("### ➕ Adicionar Nova Prova")
    
    nome_novo = st.text_input("Nome da nova prova", key="novo_nome_prova")
    data_nova = st.date_input("Data da prova", key="nova_data_prova")
    horario_novo = st.time_input(
        "Horário da prova (Fuso Horário: São Paulo/Brasil - Bloqueio de apostas após este horário)",
        pd.to_datetime("14:00:00", format="%H:%M:%S").time(),
        key="novo_horario_prova",
        help="Horário em formato 24h (ex: 14:00 para 2 PM). Apostas serão bloqueadas após este horário em qualquer fuso horário."
    )
    status_novo = st.selectbox("Status", ["Ativa", "Inativa"], key="novo_status_prova")
    tipo_novo = st.selectbox("Tipo", ["Normal", "Sprint"], key="novo_tipo_prova")

    # Base de circuitos para vínculo direto da prova.
    try:
        circuitos_df = get_circuitos_df()
    except Exception:
        circuitos_df = pd.DataFrame()

    opcoes_circuito = ["(Sem vínculo)"]
    mapa_circuito = {"(Sem vínculo)": None}
    if not circuitos_df.empty:
        for _, r in circuitos_df.iterrows():
            cid = str(r.get("circuit_id", "")).strip()
            if not cid:
                continue
            cname = str(r.get("circuit_name", cid)).strip()
            country = str(r.get("country", "")).strip()
            locality = str(r.get("locality", "")).strip()
            geo = ", ".join([x for x in [locality, country] if x])
            label = f"{cname} ({geo}) - {cid}" if geo else f"{cname} - {cid}"
            opcoes_circuito.append(label)
            mapa_circuito[label] = cid

    circuito_sel_label = st.selectbox("Circuito (base Ergast/Jolpica)", opcoes_circuito, index=0, key="novo_circuito_prova")
    circuito_sel_id = mapa_circuito.get(circuito_sel_label)
    
    # Temporada
    current_year = str(datetime.now().year)
    temporadas_add = get_season_options()
    temporada_index_add = get_default_season_index(temporadas_add, current_year=current_year)
    temporada_nova = st.selectbox("Temporada", temporadas_add, index=temporada_index_add, key="nova_temporada_prova")
    
    if st.button("➕ Adicionar prova", key="btn_add_prova", type="primary"):
        if not nome_novo:
            st.error("❌ Preencha o nome da prova.")
        else:
            data_nova_str = data_nova.strftime('%Y-%m-%d')
            horario_str_novo = horario_novo.strftime("%H:%M:%S")
            with db_connect() as conn:
                c = conn.cursor()
                cols = get_table_columns(conn, 'provas')
                
                # Verificar duplicidade (nome + data + temporada)
                if "temporada" in cols:
                    c.execute(
                        "SELECT COUNT(*) AS cnt FROM provas WHERE nome = %s AND data = %s AND temporada = %s",
                        (nome_novo, data_nova_str, temporada_nova)
                    )
                else:
                    c.execute(
                        "SELECT COUNT(*) AS cnt FROM provas WHERE nome = %s AND data = %s",
                        (nome_novo, data_nova_str)
                    )
                
                if c.fetchone()['cnt'] > 0:
                    st.error(f"❌ Já existe uma prova cadastrada com este nome e data para a temporada {temporada_nova}.")
                else:
                    # Inserir nova prova
                    if "temporada" in cols and "circuit_id" in cols:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo, temporada, circuit_id)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                            (nome_novo, data_nova_str, horario_str_novo, status_novo, tipo_novo, temporada_nova, circuito_sel_id)
                        )
                    elif "temporada" in cols:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo, temporada)
                               VALUES (%s, %s, %s, %s, %s, %s)''',
                            (nome_novo, data_nova_str, horario_str_novo, status_novo, tipo_novo, temporada_nova)
                        )
                    elif "circuit_id" in cols:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo, circuit_id)
                               VALUES (%s, %s, %s, %s, %s, %s)''',
                            (nome_novo, data_nova_str, horario_str_novo, status_novo, tipo_novo, circuito_sel_id)
                        )
                    else:
                        c.execute(
                            '''INSERT INTO provas (nome, data, horario_prova, status, tipo)
                               VALUES (%s, %s, %s, %s, %s)''',
                            (nome_novo, data_nova_str, horario_str_novo, status_novo, tipo_novo)
                        )
                    conn.commit()
                    st.success("✅ Prova adicionada com sucesso!")
                    st.cache_data.clear()
                    st.rerun()


def main():
    render_page_header(st, "Gestão de Provas")
    
    # Verificar permissão
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return
    
    # Filtro por temporada
    current_year = str(datetime.now().year)
    temporadas = get_season_options()
    default_index = get_default_season_index(temporadas, current_year=current_year)
    temporada_sel = st.selectbox("Temporada", temporadas, index=default_index, key="gestao_provas_temporada")

    if st.button("🔄 Atualiza Base de Circuitos", key="btn_atualiza_base_circuitos"):
        temporadas_existentes = set(get_temporadas_existentes_provas())
        temporadas_existentes.add(str(temporada_sel))
        try:
            temporadas_existentes.add(str(int(temporada_sel) - 1))
        except Exception:
            pass
        stats = atualizar_base_circuitos(sorted(temporadas_existentes))
        st.success(
            f"✅ Base de circuitos atualizada: {stats.get('circuitos', 0)} circuitos de {stats.get('temporadas', 0)} temporada(s)."
        )
        st.cache_data.clear()
        st.rerun()

    # Buscar provas filtradas por temporada usando helper compatível com psycopg3
    df = get_provas_df(temporada_sel)
    df = _normalizar_df_provas(df)
    
    # Criar abas
    tab_editar, tab_adicionar = st.tabs(["✏️ Editar Provas", "➕ Adicionar Nova Prova"])
    
    with tab_editar:
        _render_aba_editar(df)
    
    with tab_adicionar:
        _render_aba_adicionar()


if __name__ == "__main__":
    main()
