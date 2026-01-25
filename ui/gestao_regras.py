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
        regras_existentes = listar_regras()
        
        modo = st.radio("Modo", ["Criar Nova Regra", "Editar Regra Existente", "Excluir Regra"], horizontal=True)
        
        if modo == "Criar Nova Regra":
            regra_form(None)
        elif modo == "Editar Regra Existente":
            if not regras_existentes:
                st.warning("Nenhuma regra cadastrada para editar.")
            else:
                regras_dict = {r['nome_regra']: r['id'] for r in regras_existentes}
                regra_nome = st.selectbox("Selecione a Regra para Editar", list(regras_dict.keys()))
                regra_atual = get_regra_by_id(regras_dict[regra_nome])
                regra_form(regra_atual)
        else:
            excluir_regra_form(regras_existentes)

def regra_form(regra_atual=None):
    """Formulário unificado para criar/editar regras"""
    is_edit = regra_atual is not None
    st.write(f"### {'Editar' if is_edit else 'Criar Nova'} Regra")
    
    with st.form("form_regra"):
        nome_regra = st.text_input("Nome da Regra *", value=regra_atual['nome_regra'] if is_edit else "", placeholder="Ex: Regra 2025")
        
        col_pts1, col_pts2 = st.columns(2)
        with col_pts1:
            st.markdown("#### Configurações de Apostas")
            quantidade_fichas = st.number_input("Quantidade Total de Fichas", min_value=1, value=regra_atual['quantidade_fichas'] if is_edit else 15)
            fichas_por_piloto = st.number_input("Máximo Fichas por Piloto", min_value=1, value=regra_atual['fichas_por_piloto'] if is_edit else 15)
            mesma_equipe = st.checkbox("Permitir apostar em pilotos da mesma equipe", value=bool(regra_atual['mesma_equipe']) if is_edit else False)
            descarte = st.checkbox("Habilitar descarte do pior resultado", value=bool(regra_atual['descarte']) if is_edit else False)
            
            st.markdown("#### Pontuações Fixas")
            pontos_pole = st.number_input("Pontos por Pole Position", value=regra_atual['pontos_pole'] if is_edit else 0)
            pontos_vr = st.number_input("Pontos por Volta Rápida", value=regra_atual['pontos_vr'] if is_edit else 0)
            pontos_11 = st.number_input("Pontos por acertar o 11º Colocado", value=regra_atual['pontos_11_colocado'] if is_edit else 25)
            
        with col_pts2:
            st.markdown("#### Regras Sprint")
            regra_sprint = st.checkbox("Habilitar regras específicas para Sprint", value=bool(regra_atual['regra_sprint']) if is_edit else False)
            pontos_sprint_pole = st.number_input("Pontos Pole Sprint", value=regra_atual['pontos_sprint_pole'] if is_edit else 0)
            pontos_sprint_vr = st.number_input("Pontos VR Sprint", value=regra_atual['pontos_sprint_vr'] if is_edit else 0)
            
            st.markdown("#### Bônus e Extras")
            bonus_vencedor = st.number_input("Bônus por acertar o Vencedor", value=regra_atual['bonus_vencedor'] if is_edit else 0)
            bonus_podio_exato = st.number_input("Bônus Pódio Completo (Ordem Exata)", value=regra_atual['bonus_podio_completo'] if is_edit else 0)
            bonus_podio_qualquer = st.number_input("Bônus Pódio (Qualquer Ordem)", value=regra_atual['bonus_podio_qualquer'] if is_edit else 0)
            pontos_dobrada = st.checkbox("Habilitar Pontuação Dobrada (Ex: Corrida Final)", value=bool(regra_atual['pontos_dobrada']) if is_edit else False)
            
        st.markdown("---")
        
        with st.expander("#### Pontuação por Posição (P1 a P20)"):
            pts_pos = regra_atual['pontos_posicoes'] if is_edit and regra_atual.get('pontos_posicoes') else []
            if not pts_pos:
                pts_pos = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1] + [0]*10
                
            cols = st.columns(5)
            novos_pts_pos = []
            for i in range(20):
                with cols[i % 5]:
                    val = st.number_input(f"P{i+1}", value=pts_pos[i] if i < len(pts_pos) else 0, key=f"p{i+1}")
                    novos_pts_pos.append(val)
                    
        with st.expander("#### Pontuação Sprint (P1 a P8)"):
            pts_sp = regra_atual['pontos_sprint_posicoes'] if is_edit and regra_atual.get('pontos_sprint_posicoes') else []
            if not pts_sp:
                pts_sp = [8, 7, 6, 5, 4, 3, 2, 1]
                
            cols_sp = st.columns(4)
            novos_pts_sp = []
            for i in range(8):
                with cols_sp[i % 4]:
                    val = st.number_input(f"Sprint P{i+1}", value=pts_sp[i] if i < len(pts_sp) else 0, key=f"sp{i+1}")
                    novos_pts_sp.append(val)

        with st.expander("#### Campeonato e Penalidades"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                qto_minima_pilotos = st.number_input("Qtd Mínima de Pilotos", min_value=1, value=regra_atual['qto_minima_pilotos'] if is_edit else 3)
                penalidade_abandono = st.checkbox("Penalidade por Abandono", value=bool(regra_atual['penalidade_abandono']) if is_edit else False)
                pontos_penalidade = st.number_input("Pontos de Penalidade", value=regra_atual['pontos_penalidade'] if is_edit else 0)
            with col_c2:
                pontos_campeao = st.number_input("Pontos Campeão", value=regra_atual['pontos_campeao'] if is_edit else 150)
                pontos_vice = st.number_input("Pontos Vice", value=regra_atual['pontos_vice'] if is_edit else 100)
                pontos_equipe = st.number_input("Pontos Equipe", value=regra_atual['pontos_equipe'] if is_edit else 80)
                    
        submitted = st.form_submit_button("Salvar Regra")
        
        if submitted:
            if not nome_regra:
                st.error("Nome da regra é obrigatório!")
                return
                
            params = {
                "nome_regra": nome_regra,
                "quantidade_fichas": quantidade_fichas,
                "fichas_por_piloto": fichas_por_piloto,
                "mesma_equipe": mesma_equipe,
                "descarte": descarte,
                "pontos_pole": pontos_pole,
                "pontos_vr": pontos_vr,
                "pontos_posicoes": novos_pts_pos,
                "pontos_11_colocado": pontos_11,
                "regra_sprint": regra_sprint,
                "pontos_sprint_pole": pontos_sprint_pole,
                "pontos_sprint_vr": pontos_sprint_vr,
                "pontos_sprint_posicoes": novos_pts_sp,
                "pontos_dobrada": pontos_dobrada,
                "bonus_vencedor": bonus_vencedor,
                "bonus_podio_completo": bonus_podio_exato,
                "bonus_podio_qualquer": bonus_podio_qualquer,
                "qto_minima_pilotos": qto_minima_pilotos,
                "penalidade_abandono": penalidade_abandono,
                "pontos_penalidade": pontos_penalidade,
                "pontos_campeao": pontos_campeao,
                "pontos_vice": pontos_vice,
                "pontos_equipe": pontos_equipe
            }
            
            if is_edit:
                sucesso = atualizar_regra(regra_id=regra_atual['id'], **params)
            else:
                sucesso = criar_regra(**params)
                
            if sucesso:
                st.success(f"Regra salva com sucesso!")
                st.rerun()
            else:
                st.error("Erro ao salvar regra.")

def excluir_regra_form(regras_existentes):
    """Formulário de exclusão de regra"""
    st.write("### Excluir Regra")
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
