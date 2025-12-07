import streamlit as st
from db.backup_utils import download_db, upload_db, download_tabela, upload_tabela

def main():
    st.title("💾 Backup e Restauração do Banco de Dados BF1")
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

if __name__ == "__main__":
    main()