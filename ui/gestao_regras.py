"""
Interface de Gestão de Regras de Temporada
"""
import streamlit as st
import pandas as pd
import datetime
import json
from db.rules_utils import (
    criar_regra,
    atualizar_regra,
    excluir_regra,
    listar_regras,
    associar_regra_temporada,
    get_regra_temporada,
    get_regra_by_id
)
from db.backup_utils import list_temporadas

def main():
    """View principal de Gestão de Regras"""
    col1, col2 = st.columns([1, 16])
    
    with col1:
        st.image("BF1.jpg", width=75)
    
    with col2:
        st.title("Gestão de Regras")
    
    st.markdown("---")
    
    tabs = st.tabs(["Regras por Temporada", "Criar/Editar Regras"])
    
    # ========== ABA: Regras por Temporada ==========
    with tabs[0]:
        st.subheader("Associar Regras às Temporadas")
        
        try:
            temporadas = list_temporadas() or []
        except Exception:
            temporadas = []
            
        if not temporadas:
            ano_atual = datetime.datetime.now().year
            temporadas = [str(ano_atual - 1), str(ano_atual), str(ano_atual + 1)]
            
        regras_disponiveis = listar_regras()
        if not regras_disponiveis:
            st.warning("Nenhuma regra cadastrada. Crie uma regra na aba 'Criar/Editar Regras'.")
            return
            
        regras_nomes = {r['id']: r['nome_regra'] for r in regras_disponiveis}
        
        st.write("### Configuração Atual")
        dados_config = []
        for temp in temporadas:
            regra_atual = get_regra_temporada(temp)
            dados_config.append({
                "Temporada": temp,
                "Regra Aplicada": regra_atual['nome_regra'] if regra_atual else "Nenhuma"
            })
        
        df_config = pd.DataFrame(dados_config)
        st.table(df_config)
        
        st.write("### Associar Nova Regra")
        col_temp, col_regra = st.columns(2)
        with col_temp:
            temporada_selecionada = st.selectbox("Selecione a Temporada", temporadas, key="temp_associar")
        with col_regra:
            regra_selecionada = st.selectbox(
                "Selecione a Regra", 
                options=list(regras_nomes.keys()),
                format_func=lambda x: regras_nomes[x],
                key="regra_associar"
            )
            
        if st.button("Associar Regra à Temporada"):
            if regra_selecionada is None:
                st.error("Selecione uma regra válida.")
            elif associar_regra_temporada(temporada_selecionada, regra_selecionada):
                st.success(f"Regra '{regras_nomes[regra_selecionada]}' associada à temporada {temporada_selecionada}!")
                st.rerun()
            else:
                st.error("Erro ao associar regra à temporada.")
                
    # ========== ABA: Criar/Editar Regras ==========
    with tabs[1]:
        st.subheader("Gerenciar Regras")
        
        try:
            regras_existentes = listar_regras()
        except Exception as e:
            st.error(f"❌ Erro ao carregar regras: {e}")
            regras_existentes = []
        
        modo = st.radio("Modo", ["Criar Nova Regra", "Editar Regra Existente", "Excluir Regra"], horizontal=True)
        
        if modo == "Criar Nova Regra":
            st.write("---")
            regra_form(None)
        elif modo == "Editar Regra Existente":
            if not regras_existentes:
                st.warning("⚠️ Nenhuma regra cadastrada para editar.")
            else:
                regras_dict = {r['nome_regra']: r['id'] for r in regras_existentes}
                regra_nome = st.selectbox("Selecione a Regra para Editar", list(regras_dict.keys()))
                try:
                    regra_atual = get_regra_by_id(regras_dict[regra_nome])
                    st.write("---")
                    regra_form(regra_atual)
                except Exception as e:
                    st.error(f"❌ Erro ao carregar regra: {e}")
        else:
            st.write("---")
            excluir_regra_form(regras_existentes)

def regra_form(regra_atual=None):
    """Formulário para criar/editar regras"""
    is_edit = regra_atual is not None
    
    st.subheader(f"{'✏️ Editar' if is_edit else '➕ Criar Nova'} Regra")
    
    # Documentação
    with st.expander("📋 Parâmetros Configuráveis"):
        st.markdown("""
        **Fórmula:** Pontos = (Pontos_Piloto × Fichas) + Bônus_11º
        
        Parâmetros: 1) Nome 2) Fichas 3) Mesma Equipe 4) Fichas/Piloto 5) Descarte
        6) Pontos 11º 7) Min Pilotos 8) Penalidade 9) Pts Penalidade
        10) Regra Sprint 11) Wildcard 12) Pts Campeão 13) Pts Vice 14) Pts Equipe
        """)
    
    st.divider()
    
    # Formulário único e completo
    with st.form("form_regra", clear_on_submit=False):
        # 1. Nome da Regra
        nome_regra = st.text_input(
            "1️⃣ Nome da Regra *",
            value=regra_atual['nome_regra'] if is_edit else "",
            placeholder="Ex: BF1 2025"
        )
        
        # 2. Quantidade de Fichas
        quantidade_fichas = st.number_input(
            "2️⃣ Quantidade Total de Fichas *",
            min_value=1,
            value=regra_atual['quantidade_fichas'] if is_edit else 15,
            help="Total de fichas disponível para cada prova"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### ⚙️ Configurações Gerais")
            # 3. Mesma Equipe
            mesma_equipe = st.radio(
                "3️⃣ Permitir 2 pilotos da mesma equipe?",
                options=[True, False],
                format_func=lambda x: "Sim" if x else "Não",
                index=0 if (is_edit and regra_atual['mesma_equipe']) else 1,
                horizontal=True,
                help="Sim: máx 2 pilotos por equipe | Não: máx 1 piloto por equipe"
            )
            
            # 4. Fichas por Piloto
            fichas_por_piloto = st.number_input(
                "4️⃣ Máximo de Fichas por Piloto *",
                min_value=1,
                value=regra_atual['fichas_por_piloto'] if is_edit else 15,
                help="Nenhum piloto pode receber mais fichas que este valor"
            )
            
            # 5. Descarte
            descarte = st.radio(
                "5️⃣ Habilitar Descarte do Pior Resultado?",
                options=[True, False],
                format_func=lambda x: "Sim" if x else "Não",
                index=0 if (is_edit and regra_atual['descarte']) else 1,
                horizontal=True,
                help="Sim: remove pior resultado | Não: conta todos"
            )
            
            # 6. Pontos pelo 11º Colocado
            pontos_11_colocado = st.number_input(
                "6️⃣ Pontos pelo Acerto do 11º Colocado *",
                min_value=0,
                value=regra_atual['pontos_11_colocado'] if is_edit else 25,
                help="Bônus por acertar qual piloto fica em 11º lugar na prova"
            )
            
            # 7. Quantidade Mínima de Pilotos
            qtd_minima_pilotos = st.number_input(
                "7️⃣ Quantidade Mínima de Pilotos *",
                min_value=1,
                value=regra_atual['qtd_minima_pilotos'] if is_edit else 3,
                help="Mínimo de pilotos que o participante deve apostar por prova"
            )
        
        with col2:
            st.write("### ⚡ Penalidades & Sprint")
            # 8. Penalidade por Abandono
            penalidade_abandono = st.radio(
                "8️⃣ Penalidade por Abandono?",
                options=[True, False],
                format_func=lambda x: "Sim" if x else "Não",
                index=0 if (is_edit and regra_atual['penalidade_abandono']) else 1,
                horizontal=True,
                help="Sim: aplica penalidade ao piloto que abandona | Não: sem penalidade"
            )
            
            # 9. Pontos da Penalidade
            pontos_penalidade = st.number_input(
                "9️⃣ Pontos da Penalidade (se habilitada) *",
                value=regra_atual['pontos_penalidade'] if is_edit else 0,
                help="Quantidade de pontos deduzidos por abandono (valores negativos)"
            )
            
            # 10. Regra Sprint
            regra_sprint = st.radio(
                "🔟 Regra Especial para Sprint?",
                options=[True, False],
                format_func=lambda x: "Sim (10 fichas, mín 2 pilotos)" if x else "Não (mesma regra)",
                index=0 if (is_edit and regra_atual['regra_sprint']) else 1,
                horizontal=True,
                help="Sim: Sprint com restrições próprias | Não: mesma regra das provas normais"
            )
            
            # 11. Provas Wildcard (Pontuação Dobrada)
            pontos_dobrada = st.radio(
                "1️⃣1️⃣ Pontuação Dobrada em Sprint (Wildcard)?",
                options=[True, False],
                format_func=lambda x: "Sim (2x pontuação)" if x else "Não (1x pontuação)",
                index=0 if (is_edit and regra_atual['pontos_dobrada']) else 1,
                horizontal=True,
                help="Sprint com pontuação 2x (apenas se Regra Sprint = Sim)"
            )
            
            # 12. Pontos Campeão
            pontos_campeao = st.number_input(
                "1️⃣2️⃣ Pontos por Acertar o Campeão *",
                min_value=0,
                value=regra_atual['pontos_campeao'] if is_edit else 150,
                help="Bônus final ao final da temporada por acertar campeão"
            )
        
        st.markdown("---")
        st.write("### 🏆 Bônus de Campeonato")
        
        # 13. Pontos Vice e Equipe
        col3, col4 = st.columns(2)
        with col3:
            pontos_vice = st.number_input(
                "1️⃣3️⃣ Pontos por Acertar o Vice *",
                min_value=0,
                value=regra_atual['pontos_vice'] if is_edit else 100,
                help="Bônus final ao final da temporada por acertar vice"
            )
        
        with col4:
            pontos_equipe = st.number_input(
                "1️⃣4️⃣ Pontos por Acertar a Equipe Campeã *",
                min_value=0,
                value=regra_atual['pontos_equipe'] if is_edit else 80,
                help="Bônus final ao final da temporada por acertar equipe campeã"
            )
        
        st.markdown("---")
        
        submitted = st.form_submit_button(
            f"{'💾 Atualizar' if is_edit else '✅ Criar'} Regra",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            # Validações
            if not nome_regra or nome_regra.strip() == "":
                st.error("❌ Nome da regra é obrigatório!")
                return
            
            if fichas_por_piloto > quantidade_fichas:
                st.error(f"❌ Fichas por piloto ({fichas_por_piloto}) não pode ser maior que o total ({quantidade_fichas})")
                return
            
            if qtd_minima_pilotos > (quantidade_fichas // fichas_por_piloto):
                st.warning(f"⚠️ Aviso: mínimo de {qtd_minima_pilotos} pilotos com máx {fichas_por_piloto} fichas cada pode ser impossível com {quantidade_fichas} fichas totais")
            
            params = {
                "nome_regra": nome_regra.strip(),
                "quantidade_fichas": quantidade_fichas,
                "fichas_por_piloto": fichas_por_piloto,
                "mesma_equipe": mesma_equipe,
                "descarte": descarte,
                "pontos_pole": 0,
                "pontos_vr": 0,
                "pontos_posicoes": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                "pontos_11_colocado": pontos_11_colocado,
                "regra_sprint": regra_sprint,
                "pontos_sprint_pole": 0,
                "pontos_sprint_vr": 0,
                "pontos_sprint_posicoes": [8, 7, 6, 5, 4, 3, 2, 1],
                "pontos_dobrada": pontos_dobrada,
                "bonus_vencedor": 0,
                "bonus_podio_completo": 0,
                "bonus_podio_qualquer": 0,
                "qtd_minima_pilotos": qtd_minima_pilotos,
                "penalidade_abandono": penalidade_abandono,
                "pontos_penalidade": pontos_penalidade,
                "pontos_campeao": pontos_campeao,
                "pontos_vice": pontos_vice,
                "pontos_equipe": pontos_equipe
            }
            
            try:
                if is_edit:
                    sucesso = atualizar_regra(regra_id=regra_atual['id'], **params)
                    msg_tipo = "atualizada"
                else:
                    sucesso = criar_regra(**params)
                    msg_tipo = "criada"
                
                if sucesso:
                    st.success(f"✅ Regra '{nome_regra}' {msg_tipo} com sucesso!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ Erro ao salvar. Verifique se o nome já existe.")
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {str(e)}")

def excluir_regra_form(regras_existentes):
    """Formulário de exclusão de regra"""
    st.write("### 🗑️ Excluir Regra")
    if not regras_existentes:
        st.warning("Nenhuma regra cadastrada.")
        return
        
    regras_dict = {r['nome_regra']: r['id'] for r in regras_existentes}
    regra_nome = st.selectbox("Selecione a Regra para Excluir", list(regras_dict.keys()), key="excluir_regra_select")
    
    st.warning(f"⚠️ Confirmar exclusão da regra '{regra_nome}'?")
    if st.button("Confirmar Exclusão", type="primary"):
        if excluir_regra(regras_dict[regra_nome]):
            st.success("Regra excluída!")
            st.rerun()
        else:
            st.error("Erro ao excluir. A regra pode estar em uso.")

if __name__ == "__main__":
    main()
