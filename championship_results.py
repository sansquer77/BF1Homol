import streamlit as st
from championship_utils import save_final_results, get_final_results

def main():
    if st.session_state.get("user_role", "").strip().lower() != "master":
        st.error("Acesso restrito ao Master.")
        return

    st.title("🏆 Atualizar Resultado Final do Campeonato")

    # Exemplo: substitua pelos seus dados reais
    pilotos = ["Max Verstappen", "Lewis Hamilton", "Charles Leclerc", "Sergio Perez"]
    equipes = ["Red Bull", "Mercedes", "Ferrari", "McLaren"]

    with st.form("final_results_form"):
        campeao = st.selectbox("Piloto Campeão", pilotos)
        # Remove o campeão da lista de opções do vice
        vices_possiveis = [p for p in pilotos if p != campeao]
        vice = st.selectbox("Piloto Vice", vices_possiveis)
        equipe = st.selectbox("Equipe Campeã", equipes)
        submitted = st.form_submit_button("Salvar Resultado")
        if submitted:
            save_final_results(campeao, vice, equipe)
            st.success("Resultado oficial atualizado!")

    # Exibe o resultado atualmente armazenado
    resultado = get_final_results()
    st.subheader("Resultado Atual Armazenado")
    if resultado:
        st.markdown(f"""
        **Campeão:** {resultado['champion']}  
        **Vice:** {resultado['vice']}  
        **Equipe Campeã:** {resultado['team']}
        """)
    else:
        st.info("Nenhum resultado registrado ainda.")
