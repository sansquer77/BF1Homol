"""
Hall da Fama - Classificações Históricas
Exibe uma tabela pivot com todos os anos (colunas) e posições de classificação (linhas),
mostrando o nome do participante em cada célula para cada ano/posição.
"""

import streamlit as st
import pandas as pd
from datetime import datetime as dt_datetime
from db.db_utils import (
    db_connect,
    get_usuarios_df
)


def hall_da_fama():
    """Exibe hall da fama com histórico plurianual."""
    st.title("🏆 Hall da Fama")
    st.write("📈 Histórico de classificações por temporada - Melhores posições em cada ano")
    
    # Debug info (temporário)
    user_role = st.session_state.get('user_role', 'não definido')
    st.caption(f"🔑 Perfil atual: {user_role}")

    with db_connect() as conn:
        # Get all unique years/seasons from posicoes_participantes
        c = conn.cursor()
        c.execute("SELECT DISTINCT temporada FROM posicoes_participantes ORDER BY temporada DESC")
        seasons = [r[0] for r in c.fetchall()]
        
        # Get all users
        usuarios = get_usuarios_df()
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
        
        # Build the hall of fame table
        hall_data = []
        
        for _, user in usuarios.iterrows():
            user_id = user['id']
            user_name = user['nome']
            row = {'Participante': user_name}
            
            for season in seasons:
                c.execute('''
                    SELECT MIN(posicao) as melhor_posicao 
                    FROM posicoes_participantes 
                    WHERE usuario_id = ? AND temporada = ?
                ''', (user_id, season))
                result = c.fetchone()
                
                if result and result[0]:
                    row[season] = f"{result[0]}º"
                else:
                    row[season] = "-"
            
            hall_data.append(row)
        
        # Sort by overall best position
        def score_user(row):
            participated = sum(1 for v in row.values() if v != "-")
            best_pos = min([int(v.replace("º", "")) for v in row.values() if v != "-"], default=9999)
            return (-participated, best_pos)
        
        hall_data.sort(key=score_user)
        
        # Create DataFrame and display
        df_hall = pd.DataFrame(hall_data)
        
        st.markdown("---")
        st.subheader("📅 Classificações Históricas")
        st.dataframe(
            df_hall.set_index('Participante'),
            use_container_width=True,
            column_config={season: st.column_config.TextColumn() for season in seasons}
        )
        
        # Summary stats
        st.markdown("---")
        st.subheader("📊 Estatísticas")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Total de Participantes", len(usuarios))
        with col2:
            c.execute("SELECT COUNT(DISTINCT temporada) FROM posicoes_participantes")
            unique_seasons = c.fetchone()[0]
            st.metric("📆 Temporadas com Resultados", unique_seasons)
        with col3:
            c.execute("SELECT COUNT(*) FROM posicoes_participantes")
            total_records = c.fetchone()[0]
            st.metric("📝 Total de Registros", total_records)
        
        # Per-season breakdown
        st.markdown("---")
        st.subheader("📈 Resumo por Temporada")
        
        season_stats = []
        for season in seasons:
            c.execute('''
                SELECT COUNT(DISTINCT usuario_id) as participants,
                       MIN(posicao) as best_pos,
                       AVG(posicao) as avg_pos
                FROM posicoes_participantes
                WHERE temporada = ?
            ''', (season,))
            result = c.fetchone()
            if result:
                season_stats.append({
                    'Temporada': season,
                    'Participantes': result[0],
                    'Melhor Posição': f"{result[1]}º" if result[1] else "-",
                    'Posição Média': f"{result[2]:.1f}" if result[2] else "-"
                })
        
        if season_stats:
            st.dataframe(
                pd.DataFrame(season_stats),
                use_container_width=True,
                hide_index=True
            )
        
        # Podium view
        st.markdown("---")
        st.subheader("🏆 Podium (Melhor Posição All-Time)")
        
        c.execute('''
            SELECT u.nome, MIN(pp.posicao) as best_ever, COUNT(DISTINCT pp.temporada) as temporadas
            FROM posicoes_participantes pp
            JOIN usuarios u ON pp.usuario_id = u.id
            GROUP BY pp.usuario_id
            ORDER BY best_ever ASC, temporadas DESC
            LIMIT 10
        ''')
        
        podium = c.fetchall()
        if podium:
            medals = ['🥇', '🥈', '🥉']
            for idx, (name, best_pos, seasons_count) in enumerate(podium):
                medal = medals[idx] if idx < 3 else f"{idx + 1}."
                st.write(f"{medal} **{name}** - Melhor posição: {best_pos}º (em {seasons_count} temporadas)")
        
        # ALWAYS show admin panel for Master users
        if user_role == 'master':
            render_admin_panel(conn, seasons)


def render_admin_panel(conn, seasons):
    """Renderiza painel administrativo para usuário Master."""
    st.markdown("---")
    st.header("⚙️ Administração - Gestão de Resultados")
    st.caption("🔒 Esta área é visível apenas para usuários Master")
    
    c = conn.cursor()
    usuarios = get_usuarios_df()
    
    if usuarios.empty:
        st.error("❌ Não há usuários cadastrados no sistema. Cadastre usuários primeiro na seção 'Gestão de Usuários'.")
        return
    
    # Tab layout for better organization
    tab1, tab2, tab3 = st.tabs(["➕ Adicionar Resultado", "✏️ Editar/Deletar", "📅 Importação em Lote"])
    
    # TAB 1: Manual entry
    with tab1:
        st.subheader("➕ Adicionar Resultado Manual")
        st.write("📝 Adicione manualmente um resultado de classificação para um participante em uma temporada específica.")
        
        with st.form("form_add_manual", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_user = st.selectbox(
                    "👤 Selecione o Participante *",
                    options=usuarios['nome'].values,
                    key="manual_user"
                )
            
            with col2:
                season_year = st.number_input(
                    "📅 Ano/Temporada *",
                    min_value=1990,
                    max_value=dt_datetime.now().year + 1,
                    value=dt_datetime.now().year,
                    key="manual_season",
                    help="Digite o ano da temporada (ex: 2024)"
                )
            
            with col3:
                position = st.number_input(
                    "🏅 Posição Final *",
                    min_value=1,
                    max_value=100,
                    value=1,
                    key="manual_position",
                    help="Posição final na classificação (1º a 100º)"
                )
            
            st.markdown("---")
            submitted = st.form_submit_button("✅ Adicionar Resultado", use_container_width=True, type="primary")
            
            if submitted:
                user_id = usuarios[usuarios['nome'] == selected_user]['id'].values[0]
                
                try:
                    # Check if record already exists
                    c.execute(
                        "SELECT id, posicao FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?",
                        (user_id, str(season_year))
                    )
                    existing = c.fetchone()
                    
                    if existing:
                        st.warning(f"⚠️ **{selected_user}** já possui um registro para a temporada **{season_year}** (posição atual: {existing[1]}º). Use a aba 'Editar/Deletar' para modificar.")
                    else:
                        # Insert new record
                        c.execute(
                            """INSERT INTO posicoes_participantes 
                               (usuario_id, posicao, temporada, data_atualizacao) 
                               VALUES (?, ?, ?, ?)""",
                            (user_id, int(position), str(season_year), dt_datetime.now().isoformat())
                        )
                        conn.commit()
                        st.success(f"✅ **{selected_user}** adicionado em **{position}º** lugar na temporada **{season_year}**!")
                        st.balloons()
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao adicionar resultado: {e}")
    
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
        
        # Fetch records with filters
        query = """
            SELECT pp.id, u.nome, pp.posicao, pp.temporada, pp.data_atualizacao
            FROM posicoes_participantes pp
            JOIN usuarios u ON pp.usuario_id = u.id
            WHERE 1=1
        """
        params = []
        
        if filter_season != "Todas":
            query += " AND pp.temporada = ?"
            params.append(filter_season)
        
        if filter_user != "Todos":
            user_id = usuarios[usuarios['nome'] == filter_user]['id'].values[0]
            query += " AND pp.usuario_id = ?"
            params.append(user_id)
        
        query += " ORDER BY pp.temporada DESC, pp.posicao ASC"
        
        c.execute(query, params)
        records = c.fetchall()
        
        if records:
            st.write(f"📄 Total de registros encontrados: **{len(records)}**")
            st.markdown("---")
            
            for record_id, name, position, season, updated_at in records:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 2, 1])
                    
                    with col1:
                        st.write(f"👤 **{name}**")
                    with col2:
                        st.write(f"🏅 {position}º")
                    with col3:
                        st.write(f"📅 {season}")
                    with col4:
                        date_str = updated_at[:10] if updated_at else "N/A"
                        st.caption(f"🕒 Atualizado: {date_str}")
                    with col5:
                        if st.button("🗑️ Deletar", key=f"delete_{record_id}", type="secondary"):
                            try:
                                c.execute("DELETE FROM posicoes_participantes WHERE id = ?", (record_id,))
                                conn.commit()
                                st.success(f"✅ Registro de **{name}** ({season}) deletado!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao deletar: {e}")
                    
                    st.markdown("---")
        else:
            st.info("ℹ️ Nenhum registro encontrado com os filtros selecionados.")
    
    # TAB 3: Bulk import
    with tab3:
        st.subheader("📅 Importação em Lote")
        st.write("📤 Importe dados históricos de múltiplas temporadas de uma vez.")
        
        with st.expander("📥 Importar 20 anos de dados (2005-2024)", expanded=False):
            st.warning("""
            ⚠️ **Atenção:** Esta função importa dados fictícios para demonstração.
            
            Os dados incluem:
            - **20 temporadas** (2005-2024)
            - **10 participantes** por temporada
            - Rankings aleatórios distribuidos entre os usuários cadastrados
            
            Registros já existentes serão ignorados.
            """)
            
            if st.button("🔄 Confirmar Importação de Dados Históricos", type="primary", key="import_bulk"):
                import_historical_data(conn)


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
    existing_users = {r[0] for r in c.fetchall()}
    
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
        
        try:
            # Check if record already exists
            c.execute(
                "SELECT id FROM posicoes_participantes WHERE usuario_id = ? AND temporada = ?",
                (usuario_id, str(temporada))
            )
            if c.fetchone():
                skipped += 1
                progress_bar.progress((idx + 1) / len(historical_data))
                continue
            
            # Insert new record
            c.execute(
                """INSERT INTO posicoes_participantes 
                   (usuario_id, posicao, temporada, data_atualizacao) 
                   VALUES (?, ?, ?, ?)""",
                (usuario_id, posicao, str(temporada), dt_datetime.now().isoformat())
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