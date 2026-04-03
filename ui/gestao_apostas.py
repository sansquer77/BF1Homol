import streamlit as st
from services.data_access_apostas import (
    get_apostas_df,
    get_participantes_temporada_df,
)
from services.data_access_provas import (
    get_provas_df,
)
from services.data_access_auth import (
    usuarios_status_historico_disponivel,
)
from services.bets_write import gerar_aposta_automatica
from services.email_service import enviar_email
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options


def main():
    render_page_header(st, "Gestão de Apostas dos Participantes")

    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    # Seletor de temporada (usa temporadas da tabela; fallback fixo)
    season_options = get_season_options(fallback_years=["2025", "2026"])
    default_index = get_default_season_index(season_options)
    season = st.selectbox("Temporada", season_options, index=default_index, key="gestao_apostas_season")
    st.session_state["temporada"] = season

    if not usuarios_status_historico_disponivel():
        st.warning(
            "⚠️ Aviso técnico: histórico de status de usuários indisponível. "
            "A seleção de participantes por temporada pode considerar apenas o status atual."
        )

    # Dados filtrados por temporada
    usuarios_df = get_participantes_temporada_df(season)
    provas_df = get_provas_df(season)
    apostas_df = get_apostas_df(season)
    participantes = usuarios_df.copy()
    provas_df = provas_df.sort_values("data") if not provas_df.empty else provas_df

    st.markdown("### Apostas dos Participantes")

    aba_participante, aba_prova = st.tabs(["Por Participante", "Por Prova"])

    with aba_participante:
        st.subheader("Gerenciar Apostas de um Participante")
        if participantes.empty:
            st.info("Nenhum participante ativo encontrado para esta temporada.")
            part_nome = None
        else:
            part_nome = st.selectbox("Selecione o participante", participantes["nome"].tolist(), key="part_nome")
        if part_nome:
            part_sel = participantes[participantes["nome"] == part_nome]
            if part_sel.empty:
                st.warning("Participante selecionado não está ativo nesta temporada.")
                return
            part_row = part_sel.iloc[0]
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
                    ok, msg = gerar_aposta_automatica(part_id, prova.id, prova.nome, apostas_df, provas_df, temporada=season)
                    if ok:
                        st.cache_data.clear()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with aba_prova:
        st.subheader("Visualizar/Atribuir Apostas por Prova")
        prova_sel = st.selectbox("Selecione a prova", provas_df["nome"].tolist() if not provas_df.empty else [], key="prova_sel")
        if prova_sel:
            prova_row = provas_df[provas_df["nome"] == prova_sel].iloc[0]
            prova_id = prova_row["id"]
            apostas_df_atual = get_apostas_df(season)
            apostas_prova = apostas_df_atual[apostas_df_atual["prova_id"] == prova_id]

            participantes_lembrete = participantes.copy()
            if not participantes_lembrete.empty and "perfil" in participantes_lembrete.columns:
                participantes_lembrete = participantes_lembrete[
                    participantes_lembrete["perfil"].astype(str).str.strip().str.lower() != "master"
                ]

            usuarios_com_aposta = set(apostas_prova["usuario_id"].astype(int).tolist()) if not apostas_prova.empty else set()
            sem_aposta_df = participantes_lembrete[
                ~participantes_lembrete["id"].astype(int).isin(usuarios_com_aposta)
            ] if not participantes_lembrete.empty else participantes_lembrete

            horario_limite_texto = f"{prova_row['data']} {prova_row['horario_prova']}"
            try:
                dt_limite = dt.datetime.strptime(horario_limite_texto, "%Y-%m-%d %H:%M:%S")
                horario_limite_texto = dt_limite.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                try:
                    dt_limite = dt.datetime.strptime(horario_limite_texto, "%Y-%m-%d %H:%M")
                    horario_limite_texto = dt_limite.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass

            st.caption(f"Participantes sem aposta nesta prova: {len(sem_aposta_df)}")
            destinatarios_preview = []
            for _, row in sem_aposta_df.iterrows() if not sem_aposta_df.empty else []:
                nome_dest = str(row.get("nome", "")).strip()
                email_dest = str(row.get("email", "")).strip()
                destinatarios_preview.append({"Nome": nome_dest, "E-mail": email_dest})

            if destinatarios_preview:
                st.markdown("##### Pré-visualização dos destinatários (CCO)")
                st.dataframe(destinatarios_preview, width="stretch", hide_index=True)

            emails_cco = [d["E-mail"] for d in destinatarios_preview if d["E-mail"]]
            if not sem_aposta_df.empty and not emails_cco:
                st.warning("Há participantes sem aposta, mas sem e-mail válido para envio.")

            if st.button(
                f"📧 Enviar lembrete (CCO) - {prova_sel}",
                key=f"lembrete_cco_{prova_id}",
                disabled=not bool(emails_cco),
            ):
                if sem_aposta_df.empty:
                    st.info("Todos os participantes já registraram aposta para esta prova.")
                else:
                    if not emails_cco:
                        st.warning("Nenhum e-mail válido encontrado para os participantes sem aposta.")
                    else:
                        assunto = f"Lembrete de aposta - {prova_sel} ({season})"
                        corpo = (
                            f"<p>Olá, participante!</p>"
                            f"<p>Este é um lembrete para registrar sua aposta da prova <b>{prova_sel}</b> da temporada <b>{season}</b>.</p>"
                            f"<p><b>Horário limite (Calendário):</b> {horario_limite_texto}</p>"
                            "<p>Se você já apostou recentemente, desconsidere esta mensagem.</p>"
                            "<p>Boa sorte!</p>"
                        )
                        ok = enviar_email(
                            destinatario="",
                            assunto=assunto,
                            corpo_html=corpo,
                            cco=emails_cco,
                        )
                        if ok:
                            st.success(f"Lembrete enviado via CCO para {len(emails_cco)} participante(s) sem aposta.")
                        else:
                            st.error("Falha ao enviar e-mail de lembrete.")

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
                    ok, msg = gerar_aposta_automatica(part.id, prova_id, prova_row["nome"], apostas_df_atual, provas_df, temporada=season)
                    if ok:
                        st.cache_data.clear()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


if __name__ == "__main__":
    main()
