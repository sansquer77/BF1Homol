import streamlit as st
from utils.data_utils import (
    get_current_season,
    get_current_driver_standings,
    get_current_constructor_standings,
    get_driver_points_by_race,
    get_qualifying_vs_race_delta,
    get_fastest_lap_times,
    get_pit_stop_data
)

def main():
    """Dashboard F1 com dados em tempo real da API Ergast"""
    
    # Título com temporada atual
    try:
        season = get_current_season()
        st.title(f"🏎️ Formula 1 {season} Dashboard")
    except Exception as e:
        st.title("🏎️ Formula 1 Dashboard")
        st.error(f"❌ Erro ao carregar temporada: {str(e)}")
        return
    
    # Seção: Classificação de Pilotos
    st.subheader("🧑‍✈️ Campeonato de Pilotos")
    try:
        driver_standings = get_current_driver_standings()
        if driver_standings.empty:
            st.info("📅 Temporada ainda não iniciou ou dados não disponíveis.")
        else:
            st.dataframe(driver_standings, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de pilotos: {str(e)}")
    
    # Seção: Classificação de Construtores
    st.subheader("🏭 Campeonato de Construtores")
    try:
        constructor_standings = get_current_constructor_standings()
        if constructor_standings.empty:
            st.info("📅 Temporada ainda não iniciou ou dados não disponíveis.")
        else:
            st.dataframe(constructor_standings, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de construtores: {str(e)}")
    
    # Seção: Progresso de Pontos
    st.subheader("📈 Progressão de pontos dos pilotos ao longo das corridas")
    try:
        points_df = get_driver_points_by_race()
        if points_df.empty or len(points_df.columns) <= 2:
            st.info("📅 Nenhuma corrida realizada ainda nesta temporada.")
        else:
            st.dataframe(points_df, use_container_width=True)
            # Gráfico de linha
            chart_data = points_df.drop(columns=["Race"]).set_index("Round")
            if not chart_data.empty:
                st.line_chart(chart_data)
    except Exception as e:
        st.error(f"❌ Erro ao carregar progresso de pontos: {str(e)}")
    
    # Seção: Classificatória vs Corrida
    st.subheader("🔄 Classificatória vs Corrida (Última Prova)")
    try:
        delta_df = get_qualifying_vs_race_delta()
        if delta_df.empty:
            st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(delta_df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de classificatória: {str(e)}")
    
    # Seção: Voltas Mais Rápidas
    st.subheader("⚡ Volta mais rápida (Última Prova)")
    try:
        fastest_laps = get_fastest_lap_times()
        if fastest_laps.empty:
            st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(fastest_laps, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar voltas rápidas: {str(e)}")
    
    # Seção: Pit Stops
    st.subheader("🛑 Resumo dos Pit Stops (Última Prova)")
    try:
        pit_stops = get_pit_stop_data()
        if pit_stops.empty:
            st.info("📅 Nenhuma corrida realizada ainda ou dados não disponíveis.")
        else:
            st.dataframe(pit_stops, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de pit stops: {str(e)}")
    
    # Rodapé informativo
    st.markdown("---")
    st.caption("📊 Dados fornecidos pela API Ergast F1 | Atualizado em tempo real")

if __name__ == "__main__":
    main()
