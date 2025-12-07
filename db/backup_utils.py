import streamlit as st
import pandas as pd
import sqlite3
import os
import io  # IMPORTANTE: necessário para exportar Excel em memória
import shutil
from pathlib import Path
from datetime import datetime
from db.db_utils import db_connect
from db.db_config import DB_PATH  # Importar caminho correto do banco

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
        st.warning(f"⚠️ Arquivo do banco de dados não encontrado: {DB_PATH}")
        st.info(f"📍 Caminho esperado: {DB_PATH.absolute()}")

def upload_db():
    """Permite upload de um novo arquivo .db, substituindo o banco atual."""
    uploaded_file = st.file_uploader(
        "Faça upload de um arquivo .db para substituir todo o banco atual",
        type=["db", "sqlite"],
        key="upload_whole_db"
    )
    if uploaded_file is not None:
        # Criar backup antes de sobrescrever
        if DB_PATH.exists():
            backup_path = Path("backups")
            backup_path.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(DB_PATH, backup_path / f"backup_antes_restauracao_{timestamp}.db")
        
        # Sobrescrever banco
        with open(DB_PATH, "wb") as out:
            out.write(uploaded_file.getbuffer())
        st.success("✅ Banco de dados substituído com sucesso!")
        st.info("💾 Um backup do banco anterior foi salvo na pasta 'backups'")

def listar_tabelas():
    """Retorna o nome de todas as tabelas do banco de dados."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            tabelas = pd.read_sql(query, conn)["name"].tolist()
        return tabelas
    except Exception as e:
        st.error(f"❌ Erro ao listar tabelas: {e}")
        return []

def exportar_tabela_excel(tabela):
    """Exporta os dados da tabela como arquivo Excel em buffer de memória."""
    with db_connect() as conn:
        df = pd.read_sql(f"SELECT * FROM {tabela}", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=tabela)
    output.seek(0)
    return output

def download_tabela():
    """Interface para download de tabela específica."""
    tabelas = listar_tabelas()
    
    if not tabelas:
        st.warning("⚠️ Nenhuma tabela encontrada no banco de dados.")
        return
    
    tabela = st.selectbox("Selecione a tabela para exportar", tabelas, key="select_export")
    
    if st.button("📊 Exportar para Excel", use_container_width=True, type="primary"):
        try:
            excel_buffer = exportar_tabela_excel(tabela)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            st.download_button(
                label=f"⬇️ Baixar tabela {tabela} (.xlsx)",
                data=excel_buffer,
                file_name=f"{tabela}_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.success(f"✅ Tabela '{tabela}' exportada com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro ao exportar tabela: {e}")

def upload_tabela():
    """Interface para upload/importação de tabela específica."""
    tabelas = listar_tabelas()
    
    if not tabelas:
        st.warning("⚠️ Nenhuma tabela encontrada no banco de dados.")
        return
    
    tabela = st.selectbox("Escolha a tabela para sobrescrever:", tabelas, key="select_import")
    
    st.warning("⚠️ **Atenção:** Esta operação irá **deletar todos os dados** da tabela selecionada e substituí-los pelo conteúdo do arquivo Excel.")
    
    uploaded_file = st.file_uploader(
        f"Upload do arquivo .xlsx para substituir dados da tabela '{tabela}'",
        type=["xlsx"], 
        key="upload_one_table"
    )
    
    if uploaded_file is not None and tabela:
        if st.button("✅ Confirmar Importação", type="primary", use_container_width=True):
            try:
                df = pd.read_excel(uploaded_file)
                
                # Mostrar prévia dos dados
                st.write(f"👀 Prévia dos dados ({len(df)} linhas):")
                st.dataframe(df.head(10))
                
                # Importar para o banco
                with sqlite3.connect(DB_PATH) as conn:
                    # Fazer backup da tabela atual
                    backup_df = pd.read_sql(f"SELECT * FROM {tabela}", conn)
                    
                    # Deletar dados antigos
                    conn.execute(f"DELETE FROM {tabela}")
                    
                    # Inserir novos dados
                    df.to_sql(tabela, conn, if_exists='append', index=False)
                    
                st.success(f"✅ Tabela '{tabela}' atualizada com sucesso! {len(df)} linhas importadas.")
                st.info(f"💾 Backup da tabela anterior: {len(backup_df)} linhas")
                
            except Exception as e:
                st.error(f"❌ Erro ao importar tabela: {e}")
                st.info("💡 Verifique se as colunas do arquivo Excel correspondem às colunas da tabela.")

def main():
    st.title("💾 Backup e Restauração do Banco de Dados")
    st.markdown("""
    - **Download Completo:** Baixe uma cópia do banco inteiro (.db).
    - **Upload Completo:** Substitua todo o banco de dados por um novo arquivo.
    - **Exportar tabela:** Exporte uma tabela específica (.xlsx).
    - **Importar tabela:** Importe dados para uma tabela específica (sobrescreve).
    """)
    
    # Mostrar info do banco
    st.info(f"📍 Banco de dados: `{DB_PATH.name}` | Status: {'Existe' if DB_PATH.exists() else 'Não encontrado'}")
    
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

# ============ FUNÇÕES DE BACKUP E RESTAURAÇÃO ============

def backup_banco(backup_dir: str = "backups") -> str:
    """
    Cria um backup do banco de dados
    
    Args:
        backup_dir: Diretório para armazenar backups
    
    Returns:
        Caminho do arquivo de backup criado
    """
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"backup_{timestamp}.db"
    
    shutil.copy2(DB_PATH, backup_file)
    return str(backup_file)

def restaurar_backup(backup_file: str) -> bool:
    """
    Restaura o banco de dados a partir de um backup
    
    Args:
        backup_file: Caminho do arquivo de backup
    
    Returns:
        True se restaurado com sucesso, False caso contrário
    """
    try:
        if not Path(backup_file).exists():
            return False
        
        shutil.copy2(backup_file, DB_PATH)
        return True
    except Exception as e:
        print(f"Erro ao restaurar backup: {e}")
        return False