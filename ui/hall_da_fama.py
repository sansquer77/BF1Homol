"""
Hall da Fama - Classificações Históricas
Exibe uma tabela pivot com todos os anos (colunas) e posições de classificação (linhas),
mostrando o nome do participante em cada célula para cada ano/posição.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime as dt_datetime
from db.db_utils import (
    db_connect,
    table_exists,
    get_usuarios_df,
    get_participantes_temporada_df,
    usuarios_status_historico_disponivel
)
from utils.helpers import render_page_header


def _table_height(total_rows: int, row_height: int = 36, max_height: int = 620) -> int:
    return min(max_height, 42 + (max(total_rows, 1) * row_height))


def _resolve_hall_source(conn) -> tuple[str, str]:
    """Define a tabela fonte do Hall da Fama com fallback para legado."""
    c = conn.cursor()
    has_hall = table_exists(conn, 'hall_da_fama')
    if has_hall:
        c.execute("SELECT COUNT(*) AS cnt FROM hall_da_fama")
        hall_count = int(c.fetchone()['cnt'] or 0)
        if hall_count > 0:
            return "hall_da_fama", "posicao_final"

    has_legacy = table_exists(conn, 'posicoes_participantes')
    if has_legacy:
        c.execute("SELECT COUNT(*) AS cnt FROM posicoes_participantes")
        legacy_count = int(c.fetchone()['cnt'] or 0)
        if legacy_count > 0:
            return "posicoes_participantes", "posicao"

    return "hall_da_fama", "posicao_final"


def _hall_queries(source_table: str) -> dict[str, str]:
    if source_table == "posicoes_participantes":
        return {
            "seasons": (
                "SELECT DISTINCT temporada FROM posicoes_participantes "
                "WHERE temporada IS NOT NULL AND trim(cast(temporada as text)) != '' "
                "ORDER BY temporada DESC"
            ),
            "user_pos": (
                "SELECT posicao, pontos "
                "FROM posicoes_participantes "
                "WHERE usuario_id = %s AND temporada = %s "
                "LIMIT 1"
            ),
            "all_user_positions": (
                "SELECT usuario_id, temporada, posicao AS posicao, pontos "
                "FROM posicoes_participantes"
            ),
            "count_seasons": "SELECT COUNT(DISTINCT temporada) AS cnt FROM posicoes_participantes",
            "top_winners": (
                "SELECT u.nome, COUNT(*) as vitorias "
                "FROM posicoes_participantes hf "
                "JOIN usuarios u ON hf.usuario_id = u.id "
                "WHERE hf.posicao = 1 AND LOWER(u.perfil) != 'master' "
                "GROUP BY hf.usuario_id, u.nome "
                "ORDER BY vitorias DESC, u.nome ASC "
                "LIMIT 3"
            ),
            "season_stats": (
                "SELECT COUNT(DISTINCT usuario_id) as participants, "
                "MAX(pontos) as best_points, "
                "AVG(pontos) as avg_points "
                "FROM posicoes_participantes "
                "WHERE temporada = %s"
            ),
            "position_distribution": (
                "SELECT u.nome as nome, pp.posicao as posicao "
                "FROM posicoes_participantes pp "
                "JOIN usuarios u ON pp.usuario_id = u.id "
                "WHERE LOWER(u.perfil) != 'master'"
            ),
        }

    return {
        "seasons": (
            "SELECT DISTINCT temporada FROM hall_da_fama "
            "WHERE temporada IS NOT NULL AND trim(cast(temporada as text)) != '' "
            "ORDER BY temporada DESC"
        ),
        "user_pos": (
            "SELECT posicao_final, pontos "
            "FROM hall_da_fama "
            "WHERE usuario_id = %s AND temporada = %s "
            "LIMIT 1"
        ),
        "all_user_positions": (
            "SELECT usuario_id, temporada, posicao_final AS posicao, pontos "
            "FROM hall_da_fama"
        ),
        "count_seasons": "SELECT COUNT(DISTINCT temporada) AS cnt FROM hall_da_fama",
        "top_winners": (
            "SELECT u.nome, COUNT(*) as vitorias "
            "FROM hall_da_fama hf "
            "JOIN usuarios u ON hf.usuario_id = u.id "
            "WHERE hf.posicao_final = 1 AND LOWER(u.perfil) != 'master' "
            "GROUP BY hf.usuario_id, u.nome "
            "ORDER BY vitorias DESC, u.nome ASC "
            "LIMIT 3"
        ),
        "season_stats": (
            "SELECT COUNT(DISTINCT usuario_id) as participants, "
            "MAX(pontos) as best_points, "
            "AVG(pontos) as avg_points "
            "FROM hall_da_fama "
            "WHERE temporada = %s"
        ),
        "position_distribution": (
            "SELECT u.nome as nome, pp.posicao_final as posicao "
            "FROM hall_da_fama pp "
            "JOIN usuarios u ON pp.usuario_id = u.id "
            "WHERE LOWER(u.perfil) != 'master'"
        ),
    }


def hall_da_fama():
    """Exibe hall da fama com histórico plurianual."""
    render_page_header(st, "Hall da Fama")
    st.write("📈 Histórico de classificações por temporada - Melhores posições em cada ano")
    
    # Debug info (temporário - remover depois)
    user_role = st.session_state.get('user_role', 'não definido')
    st.caption(f"🔑 Perfil atual: {user_role}")

    with db_connect() as conn:
        source_table, _ = _resolve_hall_source(conn)
        queries = _hall_queries(source_table)
        if source_table == "posicoes_participantes":
            st.info("ℹ️ Exibindo histórico legado da tabela posicoes_participantes.")
        # Get all unique years/seasons from hall_da_fama
        c = conn.cursor()
        c.execute(queries["seasons"])
        seasons = [r['temporada'] for r in c.fetchall()]
        
        # Get all users (exclude master from historical table)
        usuarios = get_usuarios_df()
        if not usuarios.empty and 'perfil' in usuarios.columns:
            usuarios = usuarios[usuarios['perfil'].str.lower() != 'master']
        if usuarios.empty:
            st.warning("⚠️ Nenhum usuário cadastrado.")
            # Show admin panel even if no users
            if user_role == 'master':
                render_admin_panel(conn, [])
            return
        
        if not seasons:
            st.info("ℹ️ Nenhuma classificação registrada ainda.")
            # Show admin panel if Master user
            if user_role == 'master':
                render_admin_panel(conn, [])
            return
        
        st.write(f"**Temporadas disponíveis:** {', '.join(seasons)}")

        c.execute(queries["all_user_positions"])
        pos_rows = c.fetchall() or []
        pos_lookup: dict[tuple[int, str], dict[str, object]] = {
            (int(r["usuario_id"]), str(r["temporada"])): dict(r)
            for r in pos_rows
            if r.get("usuario_id") is not None and r.get("temporada") is not None
        }
        
        # Build the hall of fame table
        hall_data = []
        
        for _, user in usuarios.iterrows():
            user_id = user['id']
            user_name = user['nome']
            row = {'Participante': user_name}
            
            for season in seasons:
                result = pos_lookup.get((int(user_id), str(season)))

                if result and result.get('posicao') is not None:
                    pos_val = result['posicao']
                    pts_val = result.get('pontos') if result.get('pontos') is not None else 0
                    # Format points nicely (avoid .0 when integer)
                    try:
                        if float(pts_val).is_integer():
                            pts_display = str(int(pts_val))
                        else:
                            pts_display = f"{pts_val:.1f}"
                    except Exception:
                        pts_display = str(pts_val)
                    row[season] = f"{pos_val}º ({pts_display} pts)"
                else:
                    row[season] = "-"
            
            hall_data.append(row)
        
        # Sort by overall best position
        def score_user(row):
            # Filtra apenas valores que são números (posições), ignorando 'Participante' e outros campos
            positions = []
            for k, v in row.items():
                if k != 'Participante' and v != "-":
                    try:
                        positions.append(int(v.replace("º", "")))
                    except (ValueError, AttributeError):
                        pass  # Ignora valores que não são números
            
            participated = len(positions)
            best_pos = min(positions) if positions else 9999
            return (-participated, best_pos)
        
        hall_data.sort(key=score_user)
        
        # Create DataFrame and display
        df_hall = pd.DataFrame(hall_data)
        
        st.markdown("---")
        st.subheader("📅 Classificações Históricas")
        historico_df = df_hall.set_index('Participante')
        historico_config = {
            "_index": st.column_config.TextColumn("Participante", width="medium"),
            **{season: st.column_config.TextColumn(str(season), width="small") for season in seasons},
        }
        st.dataframe(
            historico_df,
            width="stretch",
            height=_table_height(len(historico_df), max_height=680),
            column_config=historico_config,
        )
        
        # Summary stats
        st.markdown("---")
        st.subheader("📊 Estatísticas")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            # Excluir usuário Master do total de participantes
            if 'perfil' in usuarios.columns:
                participantes_count = len(usuarios[usuarios['perfil'].str.lower() != 'master'])
            else:
                participantes_count = len(usuarios)
            st.metric("👥 Total de Participantes", participantes_count)
        with col2:
            c.execute(queries["count_seasons"])
            unique_seasons = c.fetchone()['cnt']
            st.metric("📆 Temporadas Realizadas", unique_seasons)
        with col3:
            # Maiores vencedores: top 3 participantes com mais temporadas ganhas (1º lugar)
            c.execute(queries["top_winners"])
            top_winners = c.fetchall()
            st.markdown("**🥇 Maiores Vencedores**")
            if top_winners:
                for row in top_winners:
                    name, wins = row['nome'], row['vitorias']
                    st.markdown(f"- {name} ({wins})")
            else:
                st.markdown("-")
        
        # Per-season breakdown
        st.markdown("---")
        st.subheader("📈 Resumo por Temporada")
        
        season_stats = []
        for season in seasons:
            c.execute(queries["season_stats"], (season,))
            result = c.fetchone()
            if result:
                season_stats.append({
                    'Temporada': season,
                    'Participantes': result['participants'],
                    'Maior Pontuação': f"{result['best_points']:.1f}" if result['best_points'] is not None else "-",
                    'Pontuação Média': f"{result['avg_points']:.1f}" if result['avg_points'] is not None else "-"
                })
        
        if season_stats:
            season_stats_df = pd.DataFrame(season_stats)
            st.dataframe(
                season_stats_df,
                width="stretch",
                hide_index=True,
                height=_table_height(len(season_stats_df), max_height=520),
                column_config={
                    "Temporada": st.column_config.TextColumn("Temporada", width="small"),
                    "Participantes": st.column_config.NumberColumn("Participantes", format="%d", width="small"),
                    "Maior Pontuação": st.column_config.TextColumn("Maior Pontuação", width="small"),
                    "Pontuação Média": st.column_config.TextColumn("Pontuação Média", width="small"),
                },
            )
        
        # Position distribution table + chart
        st.markdown("---")
        st.subheader("📋 Distribuição de Posições por Participante")

        # Fetch all historical positions with user names (exclude master)
        c.execute(queries["position_distribution"])
        rows = c.fetchall()
        if rows:
            df_pos_counts = pd.DataFrame(rows)
            # Pivot: rows = participante, cols = posição, values = counts
            pivot = df_pos_counts.pivot_table(index='nome', columns='posicao', aggfunc=len, fill_value=0)
            # Sort columns by position
            pivot = pivot.reindex(sorted(pivot.columns), axis=1)
            pivot_config = {
                "_index": st.column_config.TextColumn("Participante", width="medium"),
                **{
                    col: st.column_config.NumberColumn(f"{col}º", format="%d", width="small")
                    for col in pivot.columns
                },
            }
            st.dataframe(
                pivot,
                width="stretch",
                height=_table_height(len(pivot), max_height=620),
                column_config=pivot_config,
            )

            # Stacked bar chart: X=participante, Y=contagem de cada posição (empilhadas)
            try:
                # Prepare data for stacked bar chart
                df_chart = pivot.reset_index()
                df_melted = pd.melt(df_chart, id_vars=['nome'], var_name='Posição', value_name='Contagem')
                fig = px.bar(
                    df_melted, 
                    x='nome', 
                    y='Contagem', 
                    color='Posição',
                    title='Distribuição de Posições por Participante',
                    labels={'nome': 'Participante', 'Contagem': 'Contagem'},
                    barmode='stack'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, width="stretch")
            except Exception as e:
                st.info(f'Gráfico indisponível: {str(e)}')
        else:
            st.info('Ainda não há registros para gerar a distribuição de posições.')
        
        # ALWAYS show admin panel for Master users
        if user_role == 'master':
            render_admin_panel(conn, seasons)


def render_admin_panel(conn, seasons):
    """Renderiza painel administrativo para usuário Master."""
    st.markdown("---")
    st.header("⚙️ Administração - Gestão de Resultados")
    st.caption("🔒 Esta área é visível apenas para usuários Master")
    if not usuarios_status_historico_disponivel():
        st.warning(
            "⚠️ Aviso técnico: histórico de status de usuários indisponível. "
            "A listagem de participantes por temporada pode considerar apenas o status atual."
        )
    
    if 'hall_fama_season' not in st.session_state:
        st.session_state.hall_fama_season = dt_datetime.now().year

    # Season selector (shared by both tabs)
    col_season = st.columns(1)[0]
    season_year = st.number_input(
        "📅 Ano/Temporada *",
        min_value=1990,
        max_value=dt_datetime.now().year + 1,
        value=st.session_state.hall_fama_season,
        key="hall_fama_season_input",
        help="Digite o ano da temporada (ex: 2024)"
    )
    st.session_state.hall_fama_season = season_year

    c = conn.cursor()
    usuarios = get_participantes_temporada_df(str(season_year))
    
    if usuarios.empty:
        st.error("❌ Não há usuários cadastrados no sistema. Cadastre usuários primeiro na seção 'Gestão de Usuários'.")
        return
    
    # Tab layout for better organization
    tab1, tab2 = st.tabs(["➕ Adicionar Resultado", "✏️ Editar/Deletar"])
    
    # TAB 1: Manual entry with dynamic rows
    with tab1:
        st.subheader("➕ Adicionar Resultados em Lote")
        st.write("📝 Adicione múltiplos resultados de classificação para uma temporada. As linhas aparecem dinamicamente conforme você preenche.")
        
        # Initialize session state for dynamic rows
        if 'hall_fama_rows' not in st.session_state:
            st.session_state.hall_fama_rows = [{'user': None, 'position': None}] * 3
        
        st.write("**Participantes e Posições:**")
        st.write("*Preencha quantas linhas forem necessárias. Novas linhas aparecerão automaticamente.*")
        
        # Dynamic rows
        col_headers = st.columns([3, 1, 1, 0.5])
        with col_headers[0]:
            st.write("**👤 Participante**")
        with col_headers[1]:
            st.write("**🏅 Posição**")
        with col_headers[2]:
            st.write("**⭐ Pontos**")
        
        entries = []
        max_rows = len(st.session_state.hall_fama_rows)
        
        for i in range(max_rows):
            col1, col2, col3, col_spacer = st.columns([3, 1, 1, 0.5])
            
            with col1:
                selected_user = st.selectbox(
                    "Selecione",
                    options=[None] + list(usuarios['nome'].values),
                    index=0,
                    key=f"user_{i}",
                    label_visibility="collapsed"
                )
            
            with col2:
                position = st.number_input(
                    "Posição",
                    min_value=1,
                    max_value=100,
                    value=i+1,
                    key=f"pos_{i}",
                    label_visibility="collapsed"
                )

            with col3:
                pontos = st.number_input(
                    "Pontos",
                    min_value=0.0,
                    max_value=10000.0,
                    value=0.0,
                    step=0.5,
                    key=f"pts_{i}",
                    label_visibility="collapsed"
                )
            
            if selected_user:
                entries.append({'user': selected_user, 'position': position, 'points': pontos})
                
                # Se a linha atual foi preenchida e é a última, adiciona mais 3 linhas
                if i == max_rows - 1 and len(st.session_state.hall_fama_rows) < 50:
                    st.session_state.hall_fama_rows.extend([{'user': None, 'position': None}] * 3)
                    st.rerun()
        
        st.markdown("---")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Salvar Resultados", type="primary", width="stretch"):
                if not entries:
                    st.error("❌ Por favor, preencha pelo menos um participante e posição.")
                else:
                    errors = []
                    success_count = 0
                    
                    for entry in entries:
                        try:
                            user_id = usuarios[usuarios['nome'] == entry['user']]['id'].values[0]
                            user_id = int(user_id)  # Garantir tipo INTEGER para o banco
                            
                            # Check if record already exists
                            c.execute(
                                "SELECT id, posicao_final FROM hall_da_fama WHERE usuario_id = %s AND temporada = %s",
                                (user_id, str(season_year))
                            )
                            existing = c.fetchone()
                            
                            if existing:
                                errors.append(f"⚠️ **{entry['user']}** já possui registro para {season_year}")
                            else:
                                c.execute(
                                    """INSERT INTO hall_da_fama
                                       (usuario_id, posicao_final, pontos, temporada)
                                       VALUES (%s, %s, %s, %s)""",
                                    (user_id, int(entry['position']), float(entry.get('points', 0)), str(season_year))
                                )
                                success_count += 1
                        except Exception as e:
                            errors.append(f"❌ **{entry['user']}**: {str(e)}")
                    
                    conn.commit()
                    
                    if success_count > 0:
                        st.success(f"✅ {success_count} resultado(s) adicionado(s) com sucesso!")
                        st.balloons()
                        st.cache_data.clear()
                        st.session_state.hall_fama_rows = [{'user': None, 'position': None}] * 3
                        st.rerun()
                    
                    if errors:
                        st.warning("⚠️ Alguns registros não foram salvos:")
                        for error in errors:
                            st.write(error)
        
        with col_btn2:
            if st.button("🔄 Limpar Formulário", width="stretch"):
                st.session_state.hall_fama_rows = [{'user': None, 'position': None}] * 3
                st.rerun()
    
    # TAB 2: Edit/Delete
    with tab2:
        st.subheader("✏️ Gerenciar Registros Existentes")
        st.write("🗑️ Edite ou delete registros já cadastrados no Hall da Fama.")
        
        # Filter options
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            filter_season = st.selectbox(
                "📅 Filtrar por Temporada",
                options=["Todas"] + sorted(seasons, reverse=True) if seasons else ["Todas"],
                key="filter_season"
            )
        
        with col_filter2:
            filter_user = st.selectbox(
                "👤 Filtrar por Participante",
                options=["Todos"] + list(usuarios['nome'].values),
                key="filter_user"
            )
        
        # Fetch records with filters (SEM data_atualizacao)
        query = """
            SELECT pp.id, u.nome, pp.posicao_final, pp.pontos, pp.temporada
            FROM hall_da_fama pp
            JOIN usuarios u ON pp.usuario_id = u.id
            WHERE 1=1
        """
        params = []
        
        if filter_season != "Todas":
            query += " AND pp.temporada = %s"
            params.append(filter_season)
        
        if filter_user != "Todos":
            user_id = usuarios[usuarios['nome'] == filter_user]['id'].values[0]
            query += " AND pp.usuario_id = %s"
            params.append(user_id)
        
        query += " ORDER BY pp.temporada DESC, pp.posicao_final ASC"
        
        c.execute(query, params)
        records = c.fetchall()
        
        if records:
            st.write(f"📄 Total de registros encontrados: **{len(records)}**")
            st.markdown("---")
            
            for rec in records:
                record_id, name, position, points, season = rec['id'], rec['nome'], rec['posicao_final'], rec['pontos'], rec['temporada']
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
                    
                    with col1:
                        st.write(f"👤 **{name}**")
                    with col2:
                        st.write(f"🏅 {position}º")
                    with col3:
                        st.write(f"📅 {season}")
                    with col4:
                        st.write(f"⭐ {points}")
                    with col5:
                        if st.button("🗑️ Deletar", key=f"delete_{record_id}", type="secondary"):
                            try:
                                c.execute("DELETE FROM hall_da_fama WHERE id = %s", (record_id,))
                                conn.commit()
                                st.success(f"✅ Registro de **{name}** ({season}) deletado!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao deletar: {e}")

                    st.markdown("---")
        else:
            st.info("ℹ️ Nenhum registro encontrado com os filtros selecionados.")


def import_historical_data(conn):
    """Importa dados históricos de 20 anos (2005-2024)."""
    c = conn.cursor()
    
    # Dados de exemplo: 20 temporadas (2005-2024) com rankings
    historical_data = [
        # Temporada 2005
        (2005, 1, 1), (2005, 2, 2), (2005, 3, 3), (2005, 4, 4), (2005, 5, 5),
        (2005, 6, 6), (2005, 7, 7), (2005, 8, 8), (2005, 9, 9), (2005, 10, 10),
        
        # Temporada 2006
        (2006, 1, 3), (2006, 2, 1), (2006, 3, 2), (2006, 4, 5), (2006, 5, 4),
        (2006, 6, 7), (2006, 7, 6), (2006, 8, 9), (2006, 9, 8), (2006, 10, 10),
        
        # Temporada 2007
        (2007, 1, 2), (2007, 2, 3), (2007, 3, 1), (2007, 4, 6), (2007, 5, 5),
        (2007, 6, 4), (2007, 7, 8), (2007, 8, 7), (2007, 9, 10), (2007, 10, 9),
        
        # Temporada 2008
        (2008, 1, 4), (2008, 2, 2), (2008, 3, 3), (2008, 4, 1), (2008, 5, 6),
        (2008, 6, 5), (2008, 7, 9), (2008, 8, 8), (2008, 9, 7), (2008, 10, 10),
        
        # Temporada 2009
        (2009, 1, 5), (2009, 2, 4), (2009, 3, 2), (2009, 4, 3), (2009, 5, 1),
        (2009, 6, 8), (2009, 7, 7), (2009, 8, 6), (2009, 9, 9), (2009, 10, 10),
        
        # Temporada 2010
        (2010, 1, 6), (2010, 2, 5), (2010, 3, 4), (2010, 4, 2), (2010, 5, 3),
        (2010, 6, 1), (2010, 7, 9), (2010, 8, 8), (2010, 9, 10), (2010, 10, 7),
        
        # Temporada 2011
        (2011, 1, 7), (2011, 2, 6), (2011, 3, 5), (2011, 4, 4), (2011, 5, 2),
        (2011, 6, 3), (2011, 7, 1), (2011, 8, 10), (2011, 9, 8), (2011, 10, 9),
        
        # Temporada 2012
        (2012, 1, 8), (2012, 2, 7), (2012, 3, 6), (2012, 4, 5), (2012, 5, 4),
        (2012, 6, 2), (2012, 7, 3), (2012, 8, 1), (2012, 9, 10), (2012, 10, 9),
        
        # Temporada 2013
        (2013, 1, 9), (2013, 2, 8), (2013, 3, 7), (2013, 4, 6), (2013, 5, 5),
        (2013, 6, 4), (2013, 7, 2), (2013, 8, 3), (2013, 9, 1), (2013, 10, 10),
        
        # Temporada 2014
        (2014, 1, 10), (2014, 2, 9), (2014, 3, 8), (2014, 4, 7), (2014, 5, 6),
        (2014, 6, 5), (2014, 7, 4), (2014, 8, 2), (2014, 9, 3), (2014, 10, 1),
        
        # Temporada 2015
        (2015, 1, 1), (2015, 2, 10), (2015, 3, 9), (2015, 4, 8), (2015, 5, 7),
        (2015, 6, 6), (2015, 7, 5), (2015, 8, 4), (2015, 9, 2), (2015, 10, 3),
        
        # Temporada 2016
        (2016, 1, 2), (2016, 2, 1), (2016, 3, 10), (2016, 4, 9), (2016, 5, 8),
        (2016, 6, 7), (2016, 7, 6), (2016, 8, 5), (2016, 9, 4), (2016, 10, 3),
        
        # Temporada 2017
        (2017, 1, 3), (2017, 2, 2), (2017, 3, 1), (2017, 4, 10), (2017, 5, 9),
        (2017, 6, 8), (2017, 7, 7), (2017, 8, 6), (2017, 9, 5), (2017, 10, 4),
        
        # Temporada 2018
        (2018, 1, 4), (2018, 2, 3), (2018, 3, 2), (2018, 4, 1), (2018, 5, 10),
        (2018, 6, 9), (2018, 7, 8), (2018, 8, 7), (2018, 9, 6), (2018, 10, 5),
        
        # Temporada 2019
        (2019, 1, 5), (2019, 2, 4), (2019, 3, 3), (2019, 4, 2), (2019, 5, 1),
        (2019, 6, 10), (2019, 7, 9), (2019, 8, 8), (2019, 9, 7), (2019, 10, 6),
        
        # Temporada 2020
        (2020, 1, 6), (2020, 2, 5), (2020, 3, 4), (2020, 4, 3), (2020, 5, 2),
        (2020, 6, 1), (2020, 7, 10), (2020, 8, 9), (2020, 9, 8), (2020, 10, 7),
        
        # Temporada 2021
        (2021, 1, 7), (2021, 2, 6), (2021, 3, 5), (2021, 4, 4), (2021, 5, 3),
        (2021, 6, 2), (2021, 7, 1), (2021, 8, 10), (2021, 9, 9), (2021, 10, 8),
        
        # Temporada 2022
        (2022, 1, 8), (2022, 2, 7), (2022, 3, 6), (2022, 4, 5), (2022, 5, 4),
        (2022, 6, 3), (2022, 7, 2), (2022, 8, 1), (2022, 9, 10), (2022, 10, 9),
        
        # Temporada 2023
        (2023, 1, 9), (2023, 2, 8), (2023, 3, 7), (2023, 4, 6), (2023, 5, 5),
        (2023, 6, 4), (2023, 7, 3), (2023, 8, 2), (2023, 9, 1), (2023, 10, 10),
        
        # Temporada 2024
        (2024, 1, 10), (2024, 2, 9), (2024, 3, 8), (2024, 4, 7), (2024, 5, 6),
        (2024, 6, 5), (2024, 7, 4), (2024, 8, 3), (2024, 9, 2), (2024, 10, 1),
    ]
    
    # Check which users exist
    c.execute("SELECT id FROM usuarios")
    existing_users = {r['id'] for r in c.fetchall()}
    
    imported = 0
    skipped = 0
    errors = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, (temporada, usuario_id, posicao) in enumerate(historical_data):
        status_text.text(f"Processando {idx + 1}/{len(historical_data)}...")
        
        # Skip if user doesn't exist
        if usuario_id not in existing_users:
            skipped += 1
            progress_bar.progress((idx + 1) / len(historical_data))
            continue

        usuario_id = int(usuario_id)  # Garantir tipo INTEGER para o banco
        try:
            # Check if record already exists
            c.execute(
                "SELECT id FROM hall_da_fama WHERE usuario_id = %s AND temporada = %s",
                (usuario_id, str(temporada))
            )
            if c.fetchone():
                skipped += 1
                progress_bar.progress((idx + 1) / len(historical_data))
                continue
            
            # Insert new record (SEM data_atualizacao)
            c.execute(
                """INSERT INTO hall_da_fama
                   (usuario_id, posicao_final, pontos, temporada)
                   VALUES (%s, %s, %s, %s)""",
                (usuario_id, posicao, 0.0, str(temporada))
            )
            imported += 1
        except Exception as e:
            errors.append(f"usuario_id={usuario_id}, temporada={temporada}: {str(e)}")
            skipped += 1
        
        progress_bar.progress((idx + 1) / len(historical_data))
    
    conn.commit()
    progress_bar.empty()
    status_text.empty()
    
    st.success(f"""
    ✅ **Importação concluída com sucesso!**
    
    - ✅ **Importados:** {imported} registros
    - ⚠️ **Ignorados:** {skipped} registros (já existentes ou usuários inexistentes)
    """)
    
    if errors:
        with st.expander(f"⚠️ Ver {len(errors)} erros"):
            for error in errors:
                st.text(error)
    
    st.info("🔄 Recarregue a página para visualizar os dados atualizados.")
    st.cache_data.clear()


if __name__ == "__main__":
    hall_da_fama()
