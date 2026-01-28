import streamlit as st
import datetime
from utils.data_utils import (
    get_current_season,
    get_driver_standings,
    get_constructor_standings,
    get_driver_points_by_race,
    get_qualifying_vs_race_delta,
    get_fastest_lap_times,
    get_pit_stop_data
)

def main():
    """Dashboard F1 com dados em tempo real da API Ergast"""
    
    # Título principal
    st.title("🏎️ Formula 1 Dashboard")
    
    # Seletor de temporada
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Gerar lista de anos desde 1950 até ano atual
        current_year = datetime.datetime.now().year
        years = list(range(current_year, 1949, -1))  # Do atual até 1950
        
        # Obter temporada atual da API
        try:
            api_current = get_current_season()
            default_index = years.index(int(api_current)) if api_current.isdigit() else 0
        except:
            default_index = 0
        
        selected_season = st.selectbox(
            "📅 Selecione a Temporada",
            options=years,
            index=default_index,
            help="Escolha qualquer temporada desde 1950"
        )
    
    with col2:
        st.metric("Temporada Selecionada", selected_season)
    
    with col3:
        if selected_season == current_year:
            st.info("🔴 Ao Vivo")
        else:
            st.success("✅ Histórico")
    
    st.markdown("---")
    
    # Converter temporada selecionada para string
    season_str = str(selected_season)
    
    # Seção: Classificação de Pilotos
    st.subheader("🧑‍✈️ Campeonato de Pilotos")
    try:
        driver_standings = get_driver_standings(season_str)
        if driver_standings.empty:
            st.info("📅 Dados não disponíveis para esta temporada.")
        else:
            st.dataframe(driver_standings, width="stretch")
            # Exibir campeão em destaque
            if len(driver_standings) > 0:
                champion = driver_standings.iloc[0]
                st.success(f"🏆 **Campeão {selected_season}**: {champion['Driver']} ({champion['Constructor']}) - {champion['Points']} pontos")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de pilotos: {str(e)}")
    
    # Seção: Classificação de Construtores
    st.subheader("🏭 Campeonato de Construtores")
    try:
        constructor_standings = get_constructor_standings(season_str)
        if constructor_standings.empty:
            if selected_season < 1958:
                st.warning("⚠️ O Campeonato de Construtores foi criado apenas em 1958.")
            else:
                st.info("📅 Dados não disponíveis para esta temporada.")
        else:
            st.dataframe(constructor_standings, width="stretch")
            # Exibir construtor campeão em destaque
            if len(constructor_standings) > 0:
                constructor_champion = constructor_standings.iloc[0]
                st.success(f"🏆 **Construtor Campeão {selected_season}**: {constructor_champion['Constructor']} - {constructor_champion['Points']} pontos")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de construtores: {str(e)}")
    
    # Seção: Progresso de Pontos
    st.subheader("📈 Progressão de Pontos ao Longo da Temporada")
    try:
        points_df = get_driver_points_by_race(season_str)
        if points_df.empty or len(points_df.columns) <= 2:
            st.info("📅 Nenhuma corrida realizada ainda nesta temporada.")
        else:
            # Limitar número de pilotos exibidos no gráfico para melhor visualização
            with st.expander("📊 Ver Tabela Completa de Pontos"):
                st.dataframe(points_df, width="stretch")
            
            # Gráfico de linha
            chart_data = points_df.drop(columns=["Race"]).set_index("Round")
            if not chart_data.empty:
                # Seleção de pilotos para visualizar
                driver_cols = [col for col in chart_data.columns]
                if len(driver_cols) > 10:
                    st.info(f"📊 Exibindo top 10 pilotos. Use o filtro abaixo para personalizar.")
                    # Pegar top 10 por pontos finais
                    top_drivers = chart_data.iloc[-1].nlargest(10).index.tolist()
                    selected_drivers = st.multiselect(
                        "Selecione os pilotos para visualizar no gráfico",
                        options=driver_cols,
                        default=top_drivers,
                        help="Escolha até 10 pilotos para melhor visualização"
                    )
                    if selected_drivers:
                        chart_data = chart_data[selected_drivers]
                
                st.line_chart(chart_data)
    except Exception as e:
        st.error(f"❌ Erro ao carregar progresso de pontos: {str(e)}")
    
    # Seção: Classificatória vs Corrida
    st.subheader("🔄 Classificatória vs Corrida (Última Prova)")
    try:
        delta_df = get_qualifying_vs_race_delta(season_str)
        if delta_df.empty:
            st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(delta_df, width="stretch")
            # Destacar maior subida e maior queda
            if len(delta_df) > 0:
                max_gain = delta_df.loc[delta_df['Delta'].idxmax()]
                max_loss = delta_df.loc[delta_df['Delta'].idxmin()]
                col_gain, col_loss = st.columns(2)
                with col_gain:
                    st.success(f"🚀 **Maior Subida**: {max_gain['Driver']} (+{max_gain['Delta']} posições)")
                with col_loss:
                    if max_loss['Delta'] < 0:
                        st.error(f"🔻 **Maior Queda**: {max_loss['Driver']} ({max_loss['Delta']} posições)")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de classificatória: {str(e)}")
    
    # Seção: Voltas Mais Rápidas
    st.subheader("⚡ Volta Mais Rápida (Última Prova)")
    try:
        fastest_laps = get_fastest_lap_times(season_str)
        if fastest_laps.empty:
            if selected_season < 2004:
                st.warning("⚠️ Dados de volta mais rápida estão limitados para temporadas antigas.")
            else:
                st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(fastest_laps, width="stretch")
            # Destacar volta mais rápida
            if len(fastest_laps) > 0:
                fastest = fastest_laps.iloc[0]
                st.success(f"🏁 **Volta Mais Rápida**: {fastest['Driver']} - {fastest['Fastest Lap']}")
    except Exception as e:
        st.error(f"❌ Erro ao carregar voltas rápidas: {str(e)}")
    
    # Seção: Pit Stops (apenas para temporadas recentes)
    st.subheader("🛑 Resumo dos Pit Stops (Última Prova)")
    try:
        pit_stops = get_pit_stop_data(season_str)
        if pit_stops.empty:
            if selected_season < 2011:
                st.warning("⚠️ Dados de pit stops estão disponíveis apenas a partir da temporada 2011.")
            else:
                st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(pit_stops, width="stretch")
            # Estatísticas de pit stops
            if len(pit_stops) > 0:
                avg_stops = pit_stops.groupby('Driver')['Stop'].max().mean()
                st.info(f"📊 Média de paradas por piloto: {avg_stops:.2f}")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de pit stops: {str(e)}")
    
    # Rodapé informativo
    st.markdown("---")
    st.caption("""
    📊 **Fonte de Dados**: API Ergast F1 | Atualizado em tempo real  
    📝 **Observações**:
    - Dados disponíveis desde 1950
    - Campeonato de Construtores iniciou em 1958
    - Dados de pit stops disponíveis a partir de 2011
    - Alguns dados históricos podem estar incompletos
    """)

if __name__ == "__main__":
    main()
