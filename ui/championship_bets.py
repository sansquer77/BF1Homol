import streamlit as st
import pandas as pd
from services.championship_service import (
    save_championship_bet,
    get_championship_bet,
    get_championship_bet_log,
    get_championship_bets_df,
    can_place_championship_bet
)
from db.db_utils import get_pilotos_df, get_usuarios_df
from utils.season_utils import get_default_season_index, get_season_options

def main():
    st.title("📣 Apostas do Campeonato")

    # Validação da sessão do usuário
    if "user_id" not in st.session_state or "token" not in st.session_state:
        st.warning("Faça login para registrar ou visualizar apostas.")
        st.stop()

    user_id = st.session_state["user_id"]
    usuarios_df = get_usuarios_df()
    usuario = usuarios_df[usuarios_df['id'] == user_id]
    if usuario.empty:
        st.error("Usuário não encontrado.")
        st.stop()
    user_nome = usuario.iloc[0]["nome"]

    pilotos_df = get_pilotos_df()
    pilotos = sorted(pilotos_df['nome'].unique().tolist())
    equipes = sorted(pilotos_df['equipe'].unique().tolist())

    # Temporada selecionada
    temporadas = get_season_options()
    if not temporadas:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        st.stop()
    temporada_sel = st.selectbox(
        "Temporada",
        temporadas,
        index=get_default_season_index(temporadas),
        help="As apostas e logs são salvos por temporada"
    )
    if temporada_sel is None:
        st.error("Nenhuma temporada disponível.")
        st.stop()
    temporada_int = int(temporada_sel)

    # Busca aposta anterior (se houver) na temporada selecionada
    aposta_atual = get_championship_bet(user_id, temporada_int)

    st.subheader(f"Faça sua aposta para o Campeonato {temporada_int}")

    pode_apostar, msg_prazo, deadline = can_place_championship_bet(temporada_int)
    if deadline is not None:
        st.caption(f"Prazo: {deadline.strftime('%d/%m/%Y %H:%M:%S')} (SP)")
    if not pode_apostar:
        st.error(msg_prazo)
    else:
        st.info(msg_prazo)

    with st.form("form_aposta_campeonato"):
        champion = st.selectbox(
            "Piloto Campeão",
            pilotos,
            index=pilotos.index(aposta_atual["champion"]) if aposta_atual else 0
        )
        vice = st.selectbox(
            "Piloto Vice-Campeão",
            pilotos,
            index=pilotos.index(aposta_atual["vice"]) if aposta_atual else 0
        )
        team = st.selectbox(
            "Equipe Campeã de Construtores",
            equipes,
            index=equipes.index(aposta_atual["team"]) if aposta_atual else 0
        )
        submitted = st.form_submit_button("Salvar aposta", disabled=not pode_apostar)

        if submitted:
            if not champion or not vice or not team:
                st.error("Por favor, selecione todas as opções.")
            elif champion == vice:
                st.error("Campeão e vice não podem ser o mesmo piloto.")
            else:
                ok = save_championship_bet(user_id, user_nome, champion, vice, team, season=temporada_int)
                if ok:
                    st.success("Aposta de campeonato salva com sucesso!")
                else:
                    st.error("Erro ao registrar aposta.")

    # Exibir aposta atual e log
    aposta_atualizada = get_championship_bet(user_id, temporada_int)
    st.markdown(f"## Sua aposta atual ({temporada_int})")
    if aposta_atualizada:
        st.info(
            f"**Piloto Campeão:** {aposta_atualizada['champion']}  \n"
            f"**Vice-Campeão:** {aposta_atualizada['vice']}  \n"
            f"**Equipe:** {aposta_atualizada['team']}  \n"
            f"**Data/Hora:** {aposta_atualizada['bet_time']}"
        )
    else:
        st.info("Nenhuma aposta registrada ainda.")

    st.markdown(f"## Histórico de apostas no campeonato ({temporada_int})")
    log = get_championship_bet_log(user_id, temporada_int)
    if log:
        df_log = pd.DataFrame(
            log,
            columns=["Nome", "Campeão", "Vice", "Equipe", "Temporada", "Data/Hora"]
        )
        st.dataframe(df_log, width="stretch", hide_index=True)
    else:
        st.info("Nenhum histórico de apostas para este usuário.")

    # Se perfil master/admin, mostra todas as apostas
    perfil = st.session_state.get("user_role", "participante")
    if perfil in ("master", "admin"):
        st.markdown(f"## 📑 Todas as apostas do campeonato ({temporada_int}) (admin)")
        apostas_raw = get_championship_bets_df(temporada_int)
        if not isinstance(apostas_raw, pd.DataFrame):
            st.error("Formato de dados inválido para apostas do campeonato.")
            return

        apostas_df = apostas_raw
        if not apostas_df.empty:
            apostas_exibicao = pd.DataFrame(
                {
                    "Participante": apostas_df["user_nome"],
                    "Campeão": apostas_df["champion"],
                    "Vice": apostas_df["vice"],
                    "Equipe": apostas_df["team"],
                    "Temporada": apostas_df["season"],
                    "Data/Hora": apostas_df["bet_time"],
                }
            )
            st.dataframe(apostas_exibicao, width="stretch")
        else:
            st.info("Nenhuma aposta registrada por nenhum participante.")

if __name__ == "__main__":
    main()
