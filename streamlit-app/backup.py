import streamlit as st
import os

def main():

    # Título da página
    st.title("💾 Backup dos Bancos dos Dados SQLite do BF1")

    # Instruções para o usuário
    st.markdown("""
    Esta página permite que você baixe e faça upload dos bancos de dados SQLite utilizados pelo sistema.
    Certifique-se de fazer backup regularmente para evitar perda de dados.
    """)

    # Lista dos bancos definidos
    db_files = [
        ("bolao_f1.db", "Banco Principal (corridas)"),
        ("championship.db", "Banco do Campeonato")
    ]

    for db_filename, db_label in db_files:
        st.subheader(db_label)

        # Download
        if os.path.exists(db_filename):
            with open(db_filename, "rb") as fp:
                st.download_button(
                    label=f"Baixar {db_files}",
                    data=fp,
                    file_name=db_filename,
                    mime="application/octet-stream"
                )
        else:
            st.warning(f"Arquivo {db_filename} não encontrado.")

        # Upload
        uploaded_file = st.file_uploader(
            f"Faça upload do arquivo para {db_label}",
            type=["db"],
            key=f"upload_{db_filename}"
        )
        if uploaded_file is not None:
            with open(db_filename, "wb") as fp:
                fp.write(uploaded_file.getbuffer())
            st.success(f"{db_label} atualizado com sucesso!")
