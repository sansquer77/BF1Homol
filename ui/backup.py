import streamlit as st
from db.backup_utils import download_db, upload_db, download_tabela, upload_tabela, create_next_temporada, list_temporadas
from db.db_config import DB_BACKEND

def main():
    perfil = st.session_state.get("user_role", "participante")
    if perfil != "master":
        st.warning("Acesso restrito ao usuário master.")
        return

    st.title("💾 Backup e Restauração do Banco de Dados BF1")
    if DB_BACKEND == "postgres":
        st.info(
            "Ambiente PostgreSQL detectado: backup/restauração por arquivo .db está desabilitado. "
            "Use backup nativo do banco gerenciado na plataforma."
        )
    else:
        st.markdown("""
        Com este painel, você pode:
        - Baixar o banco de dados consolidado completo (.db)
        - Fazer upload ("restaurar") um banco de dados SQLite consolidado (.db)
        - Exportar e importar tabelas específicas do banco no formato Excel (.xlsx)
        """)

        st.header("Backup/Restauração do arquivo completo (.db)")
        col1, col2 = st.columns(2)
        with col1:
            download_db()
        with col2:
            upload_db()

        st.divider()
        st.header("Backup/Restauração de tabelas específicas")
        tab1, tab2 = st.tabs(["Exportar Tabela", "Importar Tabela"])
        with tab1:
            download_tabela()
        with tab2:
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