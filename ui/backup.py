import streamlit as st
from services.data_access_backup import (
    download_tabela,
    upload_tabela,
    create_next_temporada,
    download_db,
    get_postgres_backup_mode,
    list_temporadas,
    reauthorize_restore,
    upload_db,
)
from utils.helpers import render_page_header
from utils.backup_security import RestoreReauthenticationFailed, restore_authorization_error

def main():
    perfil = st.session_state.get("user_role", "participante")
    if perfil != "master":
        st.warning("Acesso restrito ao usuário master.")
        return

    render_page_header(st, "Backup e Restauração do Banco de Dados BF1")
    st.info(
        "Ambiente PostgreSQL detectado: backup/restauração completa é feita por dump SQL (.sql)."
    )
    backup_mode, backup_detail = get_postgres_backup_mode()
    if backup_mode == "full":
        st.markdown("Modo de backup: :green-badge[FULL STRUCTURE (pg_dump)]")
    else:
        st.markdown("Modo de backup: :orange-badge[DATA-ONLY (fallback)]")
    if backup_detail:
        st.caption(f"Detalhe: {backup_detail}")
    st.markdown("""
    Com este painel, você pode:
    - Baixar backup completo do PostgreSQL (.sql com INSERTs)
    - Restaurar backup completo do PostgreSQL (.sql)
    - Exportar e importar tabelas específicas em Excel (.xlsx)
    """)

    st.header("Banco Completo (.sql)")
    st.subheader("Operação segura")
    download_db()

    st.subheader("Operação crítica: restauração")
    restore_error = restore_authorization_error()
    if restore_error:
        st.warning(
            "A restauração substitui dados existentes e exige nova confirmação da senha do usuário master."
        )
        st.caption(restore_error)
        with st.form("backup_restore_reauthentication", clear_on_submit=True):
            password = st.text_input(
                "Digite novamente sua senha",
                type="password",
                max_chars=1024,
            )
            submitted = st.form_submit_button("Confirmar identidade")
        if submitted:
            try:
                reauthorize_restore(password)
            except RestoreReauthenticationFailed:
                st.error("Senha inválida ou sessão expirada.")
            except PermissionError:
                st.error("Sua sessão não está autorizada para esta operação.")
            else:
                st.success("Identidade confirmada. A restauração foi habilitada temporariamente.")
                st.rerun()
    else:
        st.warning(
            "Identidade confirmada temporariamente. A restauração substitui dados existentes."
        )
        confirmar_restore = st.checkbox(
            "Entendo o impacto e desejo habilitar a restauração do banco completo",
            value=False,
            key="backup_confirm_restore",
        )
        if confirmar_restore:
            upload_db()
        else:
            st.info("Marque a confirmação para habilitar o upload de arquivo .sql de restauração.")

    st.divider()
    st.header("Backup/Restauração de tabelas específicas")
    tab1, tab2 = st.tabs(["Exportar Tabela", "Importar Tabela"])
    with tab1:
        download_tabela()
    with tab2:
        if restore_error:
            st.info("Confirme novamente sua senha acima para importar uma tabela.")
        else:
            upload_tabela()

    st.divider()
    st.header("Temporadas")
    st.write("Gerencie as temporadas visíveis no sistema. A criação de uma nova temporada fará com que ela possa aparecer em seletores que leem a tabela `temporadas`.")
    col_a, col_b = st.columns([2, 8])
    with col_a:
        if st.button("➕ Criar próxima temporada", width="stretch"):
            new_year = create_next_temporada()
            st.success(f"✅ Temporada {new_year} criada/registrada com sucesso.")
            st.rerun()
    with col_b:
        existing = list_temporadas()
        if existing:
            st.write("Temporadas cadastradas:")
            st.write(", ".join(existing))
        else:
            st.info("Nenhuma temporada cadastrada. Botão acima cria a próxima temporada.")

if __name__ == "__main__":
    main()
