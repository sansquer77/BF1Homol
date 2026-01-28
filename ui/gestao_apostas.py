import streamlit as st
from db.db_utils import get_usuarios_df, get_provas_df, get_apostas_df
from services.bets_service import gerar_aposta_automatica

def main():
    st.title("🗂️ Gestão de Apostas dos Participantes")

    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    usuarios_df = get_usuarios_df()
    provas_df = get_provas_df()
    apostas_df = get_apostas_df()
    participantes = usuarios_df[usuarios_df['status'] == "Ativo"].copy()
    provas_df = provas_df.sort_values("data")

    st.markdown("### Apostas dos Participantes")

    aba_participante, aba_prova = st.tabs(["Por Participante", "Por Prova"])

    with aba_participante:
        st.subheader("Gerenciar Apostas de um Participante")
        part_nome = st.selectbox("Selecione o participante", participantes["nome"].tolist(), key="part_nome")
        part_row = participantes[participantes["nome"] == part_nome].iloc[0]
        part_id = part_row["id"]
        apostas_part = apostas_df[apostas_df["usuario_id"] == part_id]

        for idx, prova in enumerate(provas_df.itertuples()):
            st.markdown(f"#### {prova.nome} ({prova.data} {prova.horario_prova})")
            aposta = apostas_part[apostas_part["prova_id"] == prova.id]
            existe_aposta_manual = (
                not aposta.empty and ("automatica" not in aposta.columns or aposta.iloc[0]['automatica'] in [None, 0])
            )
            if not aposta.empty:
                aposta_view = aposta.iloc[0]
                st.success(
                    f"**Pilotos:** {aposta_view['pilotos']} \n"
                    f"**Fichas:** {aposta_view['fichas']} \n"
                    f"**11º:** {aposta_view['piloto_11']} \n"
                    f"**Data envio:** {aposta_view['data_envio']} \n"
                    f"**Automática:** {'Sim' if aposta_view['automatica'] else 'Não'}"
                )
            else:
                st.warning("Sem aposta registrada.")

            disabled_btn = existe_aposta_manual
            if st.button(
                f"Gerar aposta automática ({prova.nome})",
                key=f"auto_part_{part_id}_prova_{prova.id}_linha_{idx}",
                disabled=disabled_btn):
                ok, msg = gerar_aposta_automatica(part_id, prova.id, prova.nome, apostas_df, provas_df)
                if ok:
                    st.cache_data.clear()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with aba_prova:
        st.subheader("Visualizar/Atribuir Apostas por Prova")
        prova_sel = st.selectbox("Selecione a prova", provas_df["nome"].tolist(), key="prova_sel")
        prova_row = provas_df[provas_df["nome"] == prova_sel].iloc[0]
        prova_id = prova_row["id"]
        apostas_df = get_apostas_df()
        apostas_prova = apostas_df[apostas_df["prova_id"] == prova_id]

        for idx, part in enumerate(participantes.itertuples()):
            aposta = apostas_prova[apostas_prova["usuario_id"] == part.id]
            existe_aposta_manual = (
                not aposta.empty and ("automatica" not in aposta.columns or aposta.iloc[0]['automatica'] in [None, 0])
            )
            st.markdown(f"##### {part.nome}")
            if not aposta.empty:
                aposta_view = aposta.iloc[0]
                st.info(
                    f"**Pilotos:** {aposta_view['pilotos']} \n"
                    f"**Fichas:** {aposta_view['fichas']} \n"
                    f"**11º:** {aposta_view['piloto_11']} \n"
                    f"**Data envio:** {aposta_view['data_envio']} \n"
                    f"**Automática:** {'Sim' if aposta_view['automatica'] else 'Não'}"
                )
            else:
                st.warning("Sem aposta registrada.")

            disabled_btn = existe_aposta_manual
            if st.button(
                f"Aposta automática ({part.nome})",
                key=f"auto_prova_{prova_id}_part_{part.id}_linha_{idx}",
                disabled=disabled_btn):
                ok, msg = gerar_aposta_automatica(part.id, prova_id, prova_row["nome"], apostas_df, provas_df)
                if ok:
                    st.cache_data.clear()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

if __name__ == "__main__":
    main()
