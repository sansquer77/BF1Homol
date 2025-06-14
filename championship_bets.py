import streamlit as st
import pandas as pd
from championship_utils import (
    save_championship_bet,
    get_championship_bet,
    get_championship_bet_log
)

def main():
    st.title("Apostas no Campeonato")

    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("Faça login para apostar.")
        return

    # Exemplo: substitua por sua lógica real de extração de pilotos/equipes
    pilotos = [
    "Pierre Gasly", "Jack Doohan", "Fernando Alonso", "Lance Stroll",
    "Charles Leclerc", "Lewis Hamilton", "Esteban Ocon", "Oliver Bearman",
    "Lando Norris", "Oscar Piastri", "Kimi Antonelli", "George Russell",
    "Liam Lawson", "Isack Hadjar", "Max Verstappen", "Yuki Tsunoda",
    "Nico Hulkenberg", "Gabriel Bortoleto", "Alex Albon", "Carlos Sainz"
]
    equipes = ["Red Bull", "Mercedes", "Ferrari", "McLaren", "Alpine", "Aston Martin", "Haas", "Racing Bulls", "Sauber", "Williams"]

    # Carregar aposta anterior (se houver)
    aposta = get_championship_bet(user_id) or {}
    campeao_apostado = aposta.get('champion')
    vice_apostado = aposta.get('vice')
    equipe_apostada = aposta.get('team')

    st.subheader("Escolha seu Campeão, Vice e Equipe Campeã")

    # Selectbox para Campeão
    campeao = st.selectbox(
        "Piloto Campeão",
        pilotos,
        index=pilotos.index(campeao_apostado) if campeao_apostado in pilotos else 0,
        key="campeao"
    )

    # Remove o campeão da lista de opções do vice
    vices_possiveis = [p for p in pilotos if p != campeao]
    vice_index = vices_possiveis.index(vice_apostado) if vice_apostado in vices_possiveis else 0

    vice = st.selectbox(
        "Piloto Vice",
        vices_possiveis,
        index=vice_index,
        key="vice"
    )

    equipe_index = equipes.index(equipe_apostada) if equipe_apostada in equipes else 0
    equipe = st.selectbox(
        "Equipe Campeã",
        equipes,
        index=equipe_index,
        key="equipe"
    )

    if st.button("Salvar Aposta"):
        if campeao == vice:
            st.error("O Vice deve ser diferente do Campeão.")
        else:
            save_championship_bet(user_id, campeao, vice, equipe)
            st.success("Aposta registrada/atualizada!")

    # Log de apostas
    log = get_championship_bet_log(user_id)

    if log and all(len(entry) == 4 for entry in log):
        df_log = pd.DataFrame(log, columns=["Campeão", "Vice", "Equipe", "Data/Hora"])
        st.subheader("Histórico de Apostas no Campeonato")
        st.dataframe(df_log)
    elif log:
        st.warning("Há apostas registradas, mas alguns registros estão inconsistentes.")
    else:
        st.info("Nenhuma aposta registrada ainda.")
