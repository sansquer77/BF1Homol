import streamlit as st
import pandas as pd

from db.db_utils import db_connect, get_pilotos_df
from services.championship_service import (
    get_final_results, save_final_results
)

def main():
    st.title("Cadastrar/Atualizar Resultado Oficial do Campeonato")

    # Carregar lista completa de pilotos e equipes do banco
    pilotos_df = get_pilotos_df()
    pilotos = sorted(pilotos_df["nome"].unique())
    equipes = sorted(pilotos_df["equipe"].unique())

    # Resultado atual salvo, se houver
    resultado_atual = get_final_results()

    st.subheader("Resultado Oficial")

    col1, col2, col3 = st.columns(3)
    with col1:
        champion = st.selectbox(
            "Piloto Campeão",
            pilotos,
            index=pilotos.index(resultado_atual['champion']) if (resultado_atual and resultado_atual['champion'] in pilotos) else 0
        )
    with col2:
        vice = st.selectbox(
            "Piloto Vice",
            pilotos,
            index=pilotos.index(resultado_atual['vice']) if (resultado_atual and resultado_atual['vice'] in pilotos) else 0
        )
    with col3:
        team = st.selectbox(
            "Equipe Campeã",
            equipes,
            index=equipes.index(resultado_atual['team']) if (resultado_atual and resultado_atual['team'] in equipes) else 0
        )

    erro = None
    if st.button("Salvar resultado oficial"):
        if not champion or not vice or not team:
            erro = "Preencha todos os campos obrigatórios."
        elif champion == vice:
            erro = "Campeão e vice não podem ser o mesmo piloto."
        if erro:
            st.error(erro)
        else:
            save_final_results(champion, vice, team)
            st.success("Resultado oficial salvo/atualizado com sucesso!")
            st.rerun()

    # Exibe resultado atual
    if resultado_atual:
        st.markdown(
            f"""
            <div style='background-color:#d4edda;padding:1em;border-radius:0.5em;color:black;'>
            🏆 <b>Campeão:</b> {resultado_atual['champion']}<br>
            🥈 <b>Vice:</b> {resultado_atual['vice']}<br>
            🏭 <b>Equipe Campeã:</b> {resultado_atual['team']}
            </div>
            """,
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
