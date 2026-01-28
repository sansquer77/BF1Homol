import streamlit as st
import pandas as pd
import sqlite3
import os
import io  # IMPORTANTE: necessário para exportar Excel em memória
from pathlib import Path
from db.db_utils import db_connect

DB_PATH = Path("bolao_F1.db")

def download_db():
    """Permite fazer o download do arquivo inteiro do banco de dados SQLite."""
    if DB_PATH.exists():
        with open(DB_PATH, "rb") as fp:
            st.download_button(
                label="⬇️ Baixar banco de dados completo (.db)",
                data=fp,
                file_name=DB_PATH.name,
                mime="application/octet-stream",
                use_container_width=True
            )
    else:
        st.warning("Arquivo do banco de dados não encontrado.")

def upload_db():
    """Permite upload de um novo arquivo .db, substituindo o banco atual."""
    uploaded_file = st.file_uploader(
        "Faça upload de um arquivo .db para substituir todo o banco atual",
        type=["db", "sqlite"],
        key="upload_whole_db"
    )
    if uploaded_file is not None:
        with open(DB_PATH, "wb") as out:
            out.write(uploaded_file.getbuffer())
        st.success("Banco de dados substituído com sucesso!")

def listar_tabelas():
    """Retorna o nome de todas as tabelas do banco de dados."""
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        tabelas = pd.read_sql(query, conn)["name"].tolist()
    return tabelas

def exportar_tabela_excel(tabela):
    """Exporta os dados da tabela como arquivo Excel em buffer de memória."""
    conn = db_connect()
    df = pd.read_sql(f"SELECT * FROM {tabela}", conn)
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

def download_tabela():
    tabelas = listar_tabelas()
    tabela = st.selectbox("Selecione a tabela para exportar", tabelas, key="select_export")
    if st.button("Exportar para Excel"):
        excel_buffer = exportar_tabela_excel(tabela)
        st.download_button(
            label=f"⬇️ Baixar tabela {tabela} (.xlsx)",
            data=excel_buffer,
            file_name=f"{tabela}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def upload_tabela():
    tabelas = listar_tabelas()
    tabela = st.selectbox("Escolha a tabela para sobrescrever:", tabelas, key="select_import")
    uploaded_file = st.file_uploader(
        f"Upload do arquivo .xlsx para substituir dados da tabela '{tabela}'",
        type=["xlsx"], key="upload_one_table"
    )
    if uploaded_file is not None and tabela:
        df = pd.read_excel(uploaded_file)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(f"DELETE FROM {tabela}")
            df.to_sql(tabela, conn, if_exists='append', index=False)
        st.success(f"Tabela '{tabela}' atualizada com sucesso!")

def main():
    st.title("💾 Backup e Restauração do Banco de Dados")
    st.markdown("""
    - **Download Completo:** Baixe uma cópia do banco inteiro (.db).
    - **Upload Completo:** Substitua todo o banco de dados por um novo arquivo.
    - **Exportar tabela:** Exporte uma tabela específica (.xlsx).
    - **Importar tabela:** Importe dados para uma tabela específica (sobrescreve).
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
