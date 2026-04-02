"""
Interface de Gestão de Regras de Temporada
"""
import streamlit as st
import pandas as pd
import datetime
import json
import traceback
from db.rules_utils import (
    criar_regra,
    atualizar_regra,
    excluir_regra,
    listar_regras,
    associar_regra_temporada,
    get_regra_temporada,
    get_regra_by_id,
    listar_temporadas_por_regra,
    clonar_regra
)
from services.bets_scoring import atualizar_classificacoes_todas_as_provas
from utils.helpers import render_page_header
from utils.season_utils import get_current_year_str, get_season_options

def main():
    """View principal de Gestão de Regras"""
    perfil = st.session_state.get("user_role", "participante")
    if perfil != "master":
        st.warning("Acesso restrito ao usuário Master.")
        return
    render_page_header(st, "Gestão de Regras")
    
    st.markdown("---")
    
    tabs = st.tabs(["Regras por Temporada", "Criar/Editar Regras", "Pontuação por Posição"])    
    
    # ========== ABA: Regras por Temporada ==========
    with tabs[0]:
        st.subheader("Associar Regras às Temporadas")
        
        current_year = int(get_current_year_str())
        temporadas = get_season_options(
            fallback_years=[str(current_year - 1), str(current_year), str(current_year + 1)],
            include_current_year=True,
        )
            
        regras_disponiveis = listar_regras()
        if not regras_disponiveis:
            st.warning("Nenhuma regra cadastrada. Crie uma regra na aba 'Criar/Editar Regras'.")
            # NÃO usar return aqui - apenas não mostra o resto desta aba
        else:
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
            
            # -- Recalcular pontuação manualmente (por temporada) --
            st.markdown("---")
            st.write("### Recalcular Classificações (por Temporada)")
            st.caption("Reprocessa pontos somente para a temporada selecionada.")
            current_year = int(get_current_year_str())
            temporadas_recalc = get_season_options(
                fallback_years=[str(current_year - 1), str(current_year), str(current_year + 1)],
                include_current_year=True,
            )
            temporada_recalc = st.selectbox("Temporada para recalcular", temporadas_recalc, key="temp_recalcular")
            if st.button("Recalcular pontuação desta temporada", key="btn_recalcular_pontuacao_temp"):
                try:
                    # Limpar caches para garantir dados atualizados
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass
                    atualizar_classificacoes_todas_as_provas(temporada=temporada_recalc)
                    st.success(f"Pontuação recalculada para todas as provas da temporada {temporada_recalc}!")
                except Exception as e:
                    st.error(f"Falha ao recalcular: {e}")
                
    # ========== ABA: Criar/Editar Regras ==========
    with tabs[1]:
        st.subheader("Gerenciar Regras")
        
        try:
            regras_existentes = listar_regras()
            st.info(f"📊 {len(regras_existentes)} regra(s) cadastrada(s)")
        except Exception as e:
            st.error(f"❌ Erro ao carregar regras: {e}")
            st.code(traceback.format_exc())
            regras_existentes = []
        
        modo = st.radio("Modo", ["Criar Nova Regra", "Editar Regra Existente", "Excluir Regra"], horizontal=True)
        
        if modo == "Criar Nova Regra":
            st.write("---")
            st.info("🔧 Modo: Criar Nova Regra")
            regra_form(None)
        elif modo == "Editar Regra Existente":
            if not regras_existentes:
                st.warning("⚠️ Nenhuma regra cadastrada para editar.")
            else:
                regras_dict = {r['nome_regra']: r['id'] for r in regras_existentes}
                regra_nome = st.selectbox("Selecione a Regra para Editar", list(regras_dict.keys()))
                try:
                    regra_atual = get_regra_by_id(regras_dict[regra_nome])
                    if regra_atual:
                        st.info(f"✏️ Editando: {regra_atual.get('nome_regra', 'N/A')}")
                        st.write("---")
                        regra_form(regra_atual)
                    else:
                        st.error("❌ Regra não encontrada")
                except Exception as e:
                    st.error(f"❌ Erro ao carregar regra: {e}")
                    st.code(traceback.format_exc())
        else:
            st.write("---")
            excluir_regra_form(regras_existentes)

    # ========== ABA: Pontuação por Posição ==========
    with tabs[2]:
        st.subheader("Definir Pontos por Posição (Normal & Sprint)")
        try:
            regras_existentes = listar_regras()
        except Exception as e:
            st.error(f"❌ Erro ao carregar regras: {e}")
            regras_existentes = []

        if not regras_existentes:
            st.warning("Nenhuma regra cadastrada. Crie uma regra primeiro.")
        else:
            # Selecionar temporada primeiro e carregar a regra associada
            temporadas = get_season_options(include_current_year=False)
            if not temporadas:
                st.warning("Nenhuma temporada cadastrada na tabela 'temporadas'. Crie a temporada antes de definir pontos por posição.")
                st.stop()
            temporada_sel = st.selectbox("Temporada", temporadas, key="pont_temp_select")
            regra_atual = get_regra_temporada(temporada_sel)
            if not regra_atual:
                st.warning("Nenhuma regra associada à temporada selecionada. Associe uma regra na aba 'Regras por Temporada'.")
                st.stop()
            st.info(f"Regra atual da temporada {temporada_sel}: {regra_atual['nome_regra']}")
            tipo_prova = st.selectbox("Tipo de Prova", ["Normal", "Sprint"], key="pont_tipo_select")
            # Carrega lista atual
            pts_lista = regra_atual.get('pontos_sprint_posicoes' if tipo_prova == 'Sprint' else 'pontos_posicoes', [])
            if not isinstance(pts_lista, list):
                try:
                    pts_lista = json.loads(pts_lista)
                except Exception:
                    pts_lista = []
            # Número de posições que pontuam
            qtd_default = len([x for x in pts_lista if x and int(x) > 0]) or (8 if tipo_prova == 'Sprint' else 10)
            qtd_positions = st.number_input("Quantidade de posições que pontuam", min_value=1, max_value=20, value=qtd_default)
            # Preparar lista com zeros até 20
            pts_lista_pad = (pts_lista + [0]*20)[:20]
            # Inputs dinâmicos
            st.markdown("Insira os pontos por posição:")
            cols = st.columns(5)
            novos_pontos = []
            for i in range(qtd_positions):
                col = cols[i % 5]
                with col:
                    val = st.number_input(f"{i+1}º", min_value=0, max_value=1000, value=int(pts_lista_pad[i]), key=f"pt_pos_{tipo_prova}_{i+1}")
                    novos_pontos.append(int(val))
            # Preenche o restante com zeros
            while len(novos_pontos) < 20:
                novos_pontos.append(0)

            if st.button("Salvar Tabela de Pontos (apenas para esta temporada)", type="primary", key="btn_salvar_pontos_posicoes"):
                try:
                    # Se a regra é compartilhada entre múltiplas temporadas, clonar antes de atualizar
                    temporadas_usando = listar_temporadas_por_regra(regra_atual['id'])
                    regra_id_target = regra_atual['id']
                    if len(temporadas_usando) > 1 and temporada_sel in temporadas_usando:
                        novo_nome = f"{regra_atual['nome_regra']} - {temporada_sel}"
                        new_id = clonar_regra(regra_atual['id'], novo_nome)
                        if not new_id:
                            st.error("Falha ao clonar regra para atualização específica da temporada.")
                            st.stop()
                        # Reassocia a temporada selecionada ao clone
                        if not associar_regra_temporada(temporada_sel, new_id):
                            st.error("Falha ao associar regra clonada à temporada.")
                            st.stop()
                        regra_id_target = new_id
                        st.info(f"Regra clonada: {novo_nome}")
                    # Montar payload de atualização preservando outros campos
                    params = {
                        'regra_id': regra_id_target,
                        'nome_regra': regra_atual['nome_regra'],
                        'quantidade_fichas': regra_atual['quantidade_fichas'],
                        'fichas_por_piloto': regra_atual['fichas_por_piloto'],
                        'mesma_equipe': bool(regra_atual['mesma_equipe']),
                        'descarte': bool(regra_atual['descarte']),
                        'pontos_pole': regra_atual.get('pontos_pole', 0),
                        'pontos_vr': regra_atual.get('pontos_vr', 0),
                        'pontos_posicoes': regra_atual.get('pontos_posicoes', []),
                        'pontos_11_colocado': regra_atual['pontos_11_colocado'],
                        'regra_sprint': bool(regra_atual['regra_sprint']),
                        'pontos_sprint_pole': regra_atual.get('pontos_sprint_pole', 0),
                        'pontos_sprint_vr': regra_atual.get('pontos_sprint_vr', 0),
                        'pontos_sprint_posicoes': regra_atual.get('pontos_sprint_posicoes', []),
                        'pontos_dobrada': bool(regra_atual['pontos_dobrada']),
                        'bonus_vencedor': regra_atual.get('bonus_vencedor', 0),
                        'bonus_podio_completo': regra_atual.get('bonus_podio_completo', 0),
                        'bonus_podio_qualquer': regra_atual.get('bonus_podio_qualquer', 0),
                        'qtd_minima_pilotos': regra_atual['qtd_minima_pilotos'],
                        'penalidade_abandono': bool(regra_atual['penalidade_abandono']),
                        'pontos_penalidade': regra_atual.get('pontos_penalidade', 0),
                        'penalidade_auto_percent': regra_atual.get('penalidade_auto_percent', 20),
                        'pontos_campeao': regra_atual['pontos_campeao'],
                        'pontos_vice': regra_atual['pontos_vice'],
                        'pontos_equipe': regra_atual['pontos_equipe']
                    }
                    if tipo_prova == 'Sprint':
                        params['pontos_sprint_posicoes'] = novos_pontos
                    else:
                        params['pontos_posicoes'] = novos_pontos
                    sucesso = atualizar_regra(**params)
                    if sucesso:
                        st.success("Tabela de pontos atualizada!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Falha ao atualizar regra.")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

def safe_get(regra, key, default):
    """Helper para acessar valores de forma segura"""
    if regra is None:
        return default
    return regra.get(key, default)

def regra_form(regra_atual=None):
    """Formulário para criar/editar regras"""
    is_edit = regra_atual is not None
    
    # Debug
    if is_edit:
        st.write(f"🔍 DEBUG: regra_atual type = {type(regra_atual)}")
        if isinstance(regra_atual, dict):
            st.write(f"🔍 DEBUG: chaves disponíveis = {list(regra_atual.keys())}")
    
    st.subheader(f"{'✏️ Editar' if is_edit else '➕ Criar Nova'} Regra")
    
    # Documentação
    with st.expander("📋 Parâmetros Configuráveis"):
        st.markdown("""
        **Fórmula:** Pontos = (Pontos_Piloto × Fichas) + Bônus_11º
        
        Parâmetros: 1) Nome 2) Fichas 3) Mesma Equipe 4) Fichas/Piloto 5) Descarte
        6) Pontos 11º 7) Min Pilotos 8) Penalidade 9) Pts Penalidade
        10) Penalidade Aposta Automática (%) 11) Regra Sprint 12) Wildcard 13) Pts Campeão 14) Pts Vice 15) Pts Equipe
        """)
    
    st.divider()
    
    # Indicador de carregamento
    st.write("🟢 **Formulário carregado com sucesso**")
    
    try:
        # Formulário único e completo
        with st.form("form_regra", clear_on_submit=False):
            st.write("📋 **Preencha os campos abaixo:**")
            
            # 1. Nome da Regra
            nome_regra = st.text_input(
                "1️⃣ Nome da Regra *",
                value=safe_get(regra_atual, 'nome_regra', ""),
                placeholder="Ex: BF1 2025"
            )
            
            # 2. Quantidade de Fichas
            quantidade_fichas = st.number_input(
                "2️⃣ Quantidade Total de Fichas *",
                min_value=1,
                value=safe_get(regra_atual, 'quantidade_fichas', 15),
                help="Total de fichas disponível para cada prova"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### ⚙️ Configurações Gerais")
                # 3. Mesma Equipe
                mesma_equipe_default = safe_get(regra_atual, 'mesma_equipe', False)
                mesma_equipe = st.radio(
                    "3️⃣ Permitir 2 pilotos da mesma equipe?",
                    options=[True, False],
                    format_func=lambda x: "Sim" if x else "Não",
                    index=0 if mesma_equipe_default else 1,
                    horizontal=True,
                    help="Sim: máx 2 pilotos por equipe | Não: máx 1 piloto por equipe"
                )
                
                # 4. Fichas por Piloto
                fichas_por_piloto = st.number_input(
                    "4️⃣ Máximo de Fichas por Piloto *",
                    min_value=1,
                    value=safe_get(regra_atual, 'fichas_por_piloto', 15),
                    help="Nenhum piloto pode receber mais fichas que este valor"
                )
                
                # 5. Descarte
                descarte_default = safe_get(regra_atual, 'descarte', False)
                descarte = st.radio(
                    "5️⃣ Habilitar Descarte do Pior Resultado?",
                    options=[True, False],
                    format_func=lambda x: "Sim" if x else "Não",
                    index=0 if descarte_default else 1,
                    horizontal=True,
                    help="Sim: remove pior resultado | Não: conta todos"
                )
                
                # 6. Pontos pelo 11º Colocado
                pontos_11_colocado = st.number_input(
                    "6️⃣ Pontos pelo Acerto do 11º Colocado *",
                    min_value=0,
                    value=safe_get(regra_atual, 'pontos_11_colocado', 25),
                    help="Bônus por acertar qual piloto fica em 11º lugar na prova"
                )
                
                # 7. Quantidade Mínima de Pilotos
                qtd_minima_pilotos = st.number_input(
                    "7️⃣ Quantidade Mínima de Pilotos *",
                    min_value=1,
                    value=safe_get(regra_atual, 'qtd_minima_pilotos', 3),
                    help="Mínimo de pilotos que o participante deve apostar por prova"
                )
            
            with col2:
                st.write("### ⚡ Penalidades & Sprint")
                # 8. Penalidade por Abandono
                penalidade_default = safe_get(regra_atual, 'penalidade_abandono', False)
                penalidade_abandono = st.radio(
                    "8️⃣ Penalidade por Abandono?",
                    options=[True, False],
                    format_func=lambda x: "Sim" if x else "Não",
                    index=0 if penalidade_default else 1,
                    horizontal=True,
                    help="Sim: aplica penalidade ao piloto que abandona | Não: sem penalidade"
                )
                
                # 9. Pontos da Penalidade
                pontos_penalidade = st.number_input(
                    "9️⃣ Pontos da Penalidade (se habilitada) *",
                    value=safe_get(regra_atual, 'pontos_penalidade', 0),
                    help="Quantidade de pontos deduzidos por abandono (valores negativos)"
                )

                # 10. Penalidade por Aposta Automática (percentual)
                penalidade_auto_percent = st.number_input(
                    "🔟 Penalidade por Aposta Automática (% na 2ª+ aposta) *",
                    min_value=0,
                    max_value=100,
                    value=safe_get(regra_atual, 'penalidade_auto_percent', 20),
                    help="Percentual de redução aplicado quando a aposta é automática pela 2ª vez ou mais"
                )
                
                # 11. Regra Sprint
                sprint_default = safe_get(regra_atual, 'regra_sprint', False)
                regra_sprint = st.radio(
                    "1️⃣1️⃣ Regra Especial para Sprint?",
                    options=[True, False],
                    format_func=lambda x: "Sim (10 fichas, mín 2 pilotos)" if x else "Não (mesma regra)",
                    index=0 if sprint_default else 1,
                    horizontal=True,
                    help="Sim: Sprint com restrições próprias | Não: mesma regra das provas normais"
                )
                
                # 12. Provas Wildcard (Pontuação Dobrada)
                wildcard_default = safe_get(regra_atual, 'pontos_dobrada', False)
                pontos_dobrada = st.radio(
                    "1️⃣2️⃣ Pontuação Dobrada em Sprint (Wildcard)?",
                    options=[True, False],
                    format_func=lambda x: "Sim (2x pontuação)" if x else "Não (1x pontuação)",
                    index=0 if wildcard_default else 1,
                    horizontal=True,
                    help="Sprint com pontuação 2x (apenas se Regra Sprint = Sim)"
                )
            
            st.markdown("---")
            st.write("### 🏆 Bônus de Campeonato")
            
            # 13. Pontos Campeão, Vice e Equipe
            col3, col4, col5 = st.columns(3)
            with col3:
                pontos_campeao = st.number_input(
                    "1️⃣3️⃣ Pontos por Acertar o Campeão *",
                    min_value=0,
                    value=safe_get(regra_atual, 'pontos_campeao', 150),
                    help="Bônus final ao final da temporada por acertar campeão"
                )
            with col4:
                pontos_vice = st.number_input(
                    "1️⃣4️⃣ Pontos por Acertar o Vice *",
                    min_value=0,
                    value=safe_get(regra_atual, 'pontos_vice', 100),
                    help="Bônus final ao final da temporada por acertar vice"
                )
            
            with col5:
                pontos_equipe = st.number_input(
                    "1️⃣5️⃣ Pontos por Acertar a Equipe Campeã *",
                    min_value=0,
                    value=safe_get(regra_atual, 'pontos_equipe', 80),
                    help="Bônus final ao final da temporada por acertar equipe campeã"
                )
            
            st.markdown("---")
            
            submitted = st.form_submit_button(
                f"{'💾 Atualizar' if is_edit else '✅ Criar'} Regra",
                width="stretch",
                type="primary"
            )
            
            if submitted:
                st.write("🔄 Processando...")
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
                    "penalidade_auto_percent": penalidade_auto_percent,
                    "pontos_campeao": pontos_campeao,
                    "pontos_vice": pontos_vice,
                    "pontos_equipe": pontos_equipe
                }
                
                try:
                    if is_edit:
                        regra_id = safe_get(regra_atual, 'id', None)
                        if regra_id is None:
                            st.error("❌ ID da regra não encontrado")
                            return
                        sucesso = atualizar_regra(regra_id=regra_id, **params)
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
                    st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"❌ ERRO FATAL ao renderizar formulário: {str(e)}")
        st.code(traceback.format_exc())

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
        try:
            if excluir_regra(regras_dict[regra_nome]):
                st.success("Regra excluída!")
                st.rerun()
            else:
                st.error("Erro ao excluir. A regra pode estar em uso.")
        except Exception as e:
            st.error(f"❌ Erro ao excluir: {str(e)}")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
