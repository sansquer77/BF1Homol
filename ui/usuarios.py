import streamlit as st
import pandas as pd
from db.db_utils import get_usuarios_df, db_connect, registrar_historico_status_usuario
from services.auth_service import hash_password
from db.db_utils import get_participantes_temporada_df
from db.backup_utils import list_temporadas
from services.email_service import enviar_email
from datetime import datetime


def _ensure_gestao_financeira_table() -> None:
    with db_connect() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS financeiro_participantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                temporada TEXT NOT NULL,
                pago INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(usuario_id, temporada),
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        ''')
        conn.commit()


def _get_pagamentos_temporada(temporada: str) -> dict[int, bool]:
    _ensure_gestao_financeira_table()
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT usuario_id, pago FROM financeiro_participantes WHERE temporada = ?",
            (str(temporada),)
        )
        rows = c.fetchall()
    return {int(r[0]): bool(int(r[1])) for r in rows}


def _salvar_pagamentos_temporada(temporada: str, pagamentos: dict[int, bool]) -> None:
    _ensure_gestao_financeira_table()
    with db_connect() as conn:
        c = conn.cursor()
        for usuario_id, pago in pagamentos.items():
            c.execute(
                '''
                INSERT INTO financeiro_participantes (usuario_id, temporada, pago, atualizado_em)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(usuario_id, temporada)
                DO UPDATE SET pago = excluded.pago, atualizado_em = CURRENT_TIMESTAMP
                ''',
                (int(usuario_id), str(temporada), 1 if pago else 0)
            )
        conn.commit()


def _render_gestao_usuarios_tab(perfil: str):
    df = get_usuarios_df()
    if df.empty:
        st.info("Nenhum usuário cadastrado.")
        return

    st.markdown("### Usuários Cadastrados")
    with st.expander("Lista Completa de Usuários", expanded=True):
        show_df = df[["id", "nome", "email", "perfil", "status"]].copy()
        show_df.columns = ["ID", "Nome", "Email", "Perfil", "Status"]
        st.dataframe(show_df, width="stretch")

    st.markdown("### Editar Usuário")

    usuarios = df["nome"].tolist()
    selected = st.selectbox("Selecione um usuário para editar", usuarios)
    user_row = df[df["nome"] == selected].iloc[0]

    # Campos de edição
    novo_nome = st.text_input("Nome", user_row["nome"])
    novo_email = st.text_input("Email", user_row["email"])
    novo_perfil = st.selectbox("Perfil", ["participante", "admin", "master"], index=["participante", "admin", "master"].index(user_row["perfil"]))
    novo_status = st.selectbox("Status", ["Ativo", "Inativo"], index=0 if user_row["status"] == "Ativo" else 1)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Atualizar usuário"):
            status_anterior = str(user_row["status"]).strip()
            with db_connect() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE usuarios SET nome=?, email=?, perfil=?, status=? WHERE id=?",
                    (novo_nome, novo_email, novo_perfil, novo_status, int(user_row["id"]))
                )
                conn.commit()
            if status_anterior != novo_status:
                alterado_por = st.session_state.get("user_id")
                registrar_historico_status_usuario(
                    int(user_row["id"]),
                    novo_status,
                    alterado_por=alterado_por,
                    motivo="gestao_usuarios"
                )
            st.success("Usuário atualizado!")
            st.cache_data.clear()
            st.rerun()

    with col2:
        if "alterar_senha" not in st.session_state:
            st.session_state["alterar_senha"] = False

        if st.button("Alterar senha do usuário"):
            st.session_state["alterar_senha"] = True

        if st.session_state["alterar_senha"]:
            nova_senha = st.text_input("Nova senha", type="password", key="senha_reset")
            if st.button("Salvar nova senha"):
                if not nova_senha:
                    st.error("Digite a nova senha.")
                else:
                    nova_hash = hash_password(nova_senha)
                    with db_connect() as conn:
                        c = conn.cursor()
                        c.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (nova_hash, int(user_row["id"])))
                        conn.commit()
                    st.success("Senha atualizada com sucesso!")
                    st.session_state["alterar_senha"] = False
                    
                    # TODO: add email and password validation to user management
                    # Use utils.validators in the user management interface to ensure that new
                    # users are created with valid email formats and strong passwords. This
                    # addresses vulnerabilities related to predictable/default credentials.
                    st.rerun()
            if st.button("Cancelar alteração de senha"):
                st.session_state["alterar_senha"] = False

    st.markdown("### Excluir usuário")
    if perfil == "master":
        if st.button("Excluir usuário selecionado"):
            if user_row["perfil"] == "master":
                st.error("Não é possível excluir um usuário master.")
            else:
                with db_connect() as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM usuarios WHERE id=?", (int(user_row["id"]),))
                    conn.commit()
                st.success("Usuário excluído com sucesso!")
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    st.markdown("### Adicionar Novo Usuário")
    nome_novo = st.text_input("Nome completo", key="novo_nome")
    email_novo = st.text_input("Email", key="novo_email")
    senha_novo = st.text_input("Senha", type="password", key="nova_senha")
    perfil_novo = st.selectbox("Perfil", ["participante", "admin", "master"], key="novo_perfil")
    status_novo = st.selectbox("Status", ["Ativo", "Inativo"], key="novo_status")

    if st.button("Adicionar usuário"):
        if not nome_novo or not email_novo or not senha_novo:
            st.error("Preencha todos os campos obrigatórios.")
        else:
            from services.auth_service import cadastrar_usuario
            sucesso = cadastrar_usuario(nome_novo, email_novo, senha_novo, perfil=perfil_novo, status=status_novo)
            if sucesso:
                st.success("Usuário adicionado com sucesso!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Email já cadastrado.")


def _render_gestao_financeira_tab():
    st.subheader("Gestão financeira")

    current_year = str(datetime.now().year)
    try:
        season_options = list_temporadas() or []
    except Exception:
        season_options = []
    if current_year not in season_options:
        season_options.append(current_year)
    season_options = sorted({str(s) for s in season_options})
    temporada = st.selectbox(
        "Temporada",
        season_options,
        index=season_options.index(current_year) if current_year in season_options else 0,
        key="usuarios_finance_temporada",
    )

    participantes = get_participantes_temporada_df(temporada)
    if not participantes.empty and "status" in participantes.columns:
        participantes = participantes[
            participantes["status"].astype(str).str.strip().str.lower() == "ativo"
        ]
    if not participantes.empty and "perfil" in participantes.columns:
        participantes = participantes[
            participantes["perfil"].astype(str).str.strip().str.lower() != "master"
        ]
    participantes = participantes.sort_values("nome") if not participantes.empty else participantes

    if participantes.empty:
        st.info("Não há participantes ativos nesta temporada.")
        return

    pagamentos_db = _get_pagamentos_temporada(temporada)
    pagamentos_tela: dict[int, bool] = {}
    destinatarios_pendentes = []

    st.markdown("### Participantes ativos")
    mostrar_apenas_devendo = st.checkbox(
        "Mostrar apenas devendo",
        value=False,
        key=f"finance_show_only_pending_{temporada}",
    )

    for _, part in participantes.iterrows():
        try:
            usuario_id = int(str(part.get("id", "")).strip())
        except Exception:
            continue
        email = str(part.get("email", "") or "").strip()
        pago_default = bool(pagamentos_db.get(usuario_id, False))

        if mostrar_apenas_devendo and pago_default:
            continue

        pago_tela = st.checkbox(
            f"{part.get('nome', 'Participante')} ({email if email else 'sem e-mail'})",
            value=pago_default,
            key=f"finance_pago_{temporada}_{usuario_id}",
        )
        pagamentos_tela[usuario_id] = pago_tela
        if not pago_tela:
            destinatarios_pendentes.append({
                "Nome": str(part.get("nome", "Participante")),
                "E-mail": email,
            })

    total_ativos = len(participantes)
    total_pagos = sum(1 for v in pagamentos_tela.values() if v)
    total_devendo = total_ativos - total_pagos

    c1, c2, c3 = st.columns(3)
    c1.metric("Ativos na temporada", total_ativos)
    c2.metric("Pagaram", total_pagos)
    c3.metric("Devendo", total_devendo)

    col_save, col_mail = st.columns(2)
    with col_save:
        if st.button("Salvar status de pagamento", key="finance_save"):
            _salvar_pagamentos_temporada(temporada, pagamentos_tela)
            st.success("Status financeiro salvo com sucesso!")

    pendentes_preview = [d for d in destinatarios_pendentes if d["E-mail"]]
    st.markdown("### Pendentes para lembrete")
    if destinatarios_pendentes:
        st.dataframe(destinatarios_pendentes, width="stretch", hide_index=True)
    else:
        st.info("Nenhum participante está devendo nesta temporada.")

    with col_mail:
        if st.button(
            "Enviar lembrete financeiro (CCO)",
            key="finance_email",
            disabled=not bool(pendentes_preview),
        ):
            assunto = f"Lembrete cordial - taxa da temporada {temporada}"
            corpo = (
                "<p>Olá, participante!</p>"
                f"<p>Este é um lembrete cordial sobre a taxa da temporada <b>{temporada}</b>.</p>"
                "<p>Se o pagamento já foi realizado recentemente, por favor desconsidere esta mensagem.</p>"
                "<p>Em caso de dúvida, entre em contato com a administração.</p>"
                "<p>Obrigado!</p>"
            )
            ok = enviar_email(
                destinatario="",
                assunto=assunto,
                corpo_html=corpo,
                cco=[d["E-mail"] for d in pendentes_preview],
            )
            if ok:
                st.success(f"Lembrete enviado em CCO para {len(pendentes_preview)} participante(s).")
            else:
                st.error("Falha ao enviar lembrete financeiro.")

def main():
    st.title("👥 Gestão de Usuários")

    # Definir permissões necessárias: apenas master pode editar tudo, admin pode ver; participante não acessa
    perfil = st.session_state.get("user_role", "participante")
    if perfil not in ("admin", "master"):
        st.warning("Acesso restrito a administradores.")
        return

    aba_usuarios, aba_financeira = st.tabs(["Gestão de Usuários", "Gestão financeira"])
    with aba_usuarios:
        _render_gestao_usuarios_tab(perfil)
    with aba_financeira:
        _render_gestao_financeira_tab()

if __name__ == "__main__":
    main()
