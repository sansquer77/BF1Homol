import streamlit as st
from data_utils import (
    get_current_season,
    get_current_driver_standings,
    get_current_constructor_standings,
    get_driver_points_by_race,
    get_qualifying_vs_race_delta,
    get_fastest_lap_times,
    get_pit_stop_data
)
def main():    
    # Page Title with current season
    season = get_current_season()
    st.title(f"🏎️ Formula 1 {season} Dashboard")
    
    # Section: Driver Standings
    st.subheader("🧑‍✈️ Campeonato de Pilotos")
    st.dataframe(get_current_driver_standings(), use_container_width=True)
    
    # Section: Constructor Standings
    st.subheader("🏭 Campeonato de Construtores")
    st.dataframe(get_current_constructor_standings(), use_container_width=True)
    
    # Section: Driver Points Over Races
    st.subheader("📈 Progressão de pontos dos pilotos ao longo das corridas")
    points_df = get_driver_points_by_race()
    st.dataframe(points_df, use_container_width=True)
    st.line_chart(points_df.drop(columns=["Race"]).set_index("Round"))
    
    # Section: Qualifying vs Race Position Delta
    st.subheader("🔄 Classificação vs Corrida (Última Prova)")
    st.dataframe(get_qualifying_vs_race_delta(), use_container_width=True)
    
    # Section: Fastest Laps
    st.subheader("⚡ Volta mais rápida (Última Prova)")
    st.dataframe(get_fastest_lap_times(), use_container_width=True)
    
    # Section: Pit Stop Summary
    st.subheader("🛑 Resumo dos Pit Stops (Última Prova)")
    st.dataframe(get_pit_stop_data(), use_container_width=True)
