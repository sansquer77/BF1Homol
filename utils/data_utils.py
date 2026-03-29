import datetime
import re
from collections import defaultdict
from typing import Optional

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://api.jolpi.ca/ergast/f1"
REQUEST_TIMEOUT = 10
_SESSION = requests.Session()


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_driver_name(name: str) -> str:
    txt = str(name or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def _extract_driver_name(driver_obj: dict) -> str:
    return f"{driver_obj.get('givenName', '')} {driver_obj.get('familyName', '')}".strip()


def _status_is_finished(status: str) -> bool:
    s = str(status or "").strip().lower()
    return s == "finished" or s.startswith("+")


def _request_json(url: str) -> Optional[dict]:
    try:
        response = _SESSION.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None
    except ValueError:
        return None


def _resolve_season(season: str) -> str:
    if season != "current":
        return season
    return get_current_season()


@st.cache_data(ttl=900, show_spinner=False)
def get_current_season() -> str:
    """Obtém a temporada atual da F1."""
    data = _request_json(f"{BASE_URL}/current.json")
    if not data:
        return str(datetime.datetime.now().year)
    try:
        return str(data["MRData"]["RaceTable"]["season"])
    except (KeyError, TypeError):
        return str(datetime.datetime.now().year)

# 2. Get driver standings by season
@st.cache_data(ttl=600, show_spinner=False)
def get_driver_standings(season: str = 'current') -> pd.DataFrame:
    """Obtém classificação de pilotos por temporada
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    """
    columns = ['Position', 'Driver', 'Points', 'Wins', 'Nationality', 'Constructor']
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/driverStandings.json")
    if not data:
        return _empty_df(columns)

    try:
        standings_lists = data['MRData']['StandingsTable'].get('StandingsLists', [])
        standings = standings_lists[0].get('DriverStandings', []) if standings_lists else []
    except (KeyError, TypeError, IndexError):
        return _empty_df(columns)

    if not standings:
        return _empty_df(columns)

    drivers = []
    for item in standings:
        driver = item.get('Driver', {})
        constructors = item.get('Constructors') or []
        constructor = constructors[0] if constructors else {'name': 'N/A'}
        drivers.append({
            'Position': _safe_int(item.get('position')),
            'Driver': f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
            'Points': _safe_int(item.get('points')),
            'Wins': _safe_int(item.get('wins')),
            'Nationality': str(driver.get('nationality', 'N/A')),
            'Constructor': str(constructor.get('name', 'N/A')),
        })

    return pd.DataFrame(drivers, columns=columns)

# Alias para compatibilidade
def get_current_driver_standings():
    """Alias para manter compatibilidade com código existente"""
    return get_driver_standings('current')

# 3. Get constructor standings by season
@st.cache_data(ttl=600, show_spinner=False)
def get_constructor_standings(season: str = 'current') -> pd.DataFrame:
    """Obtém classificação de construtores por temporada
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    """
    columns = ['Position', 'Constructor', 'Points', 'Wins', 'Nationality']
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/constructorStandings.json")
    if not data:
        return _empty_df(columns)

    try:
        standings_lists = data['MRData']['StandingsTable'].get('StandingsLists', [])
        standings = standings_lists[0].get('ConstructorStandings', []) if standings_lists else []
    except (KeyError, TypeError, IndexError):
        return _empty_df(columns)

    if not standings:
        return _empty_df(columns)

    constructors = []
    for item in standings:
        constructor = item.get('Constructor', {})
        constructors.append({
            'Position': _safe_int(item.get('position')),
            'Constructor': str(constructor.get('name', 'N/A')),
            'Points': _safe_int(item.get('points')),
            'Wins': _safe_int(item.get('wins')),
            'Nationality': str(constructor.get('nationality', 'N/A')),
        })

    return pd.DataFrame(constructors, columns=columns)

# Alias para compatibilidade
def get_current_constructor_standings():
    """Alias para manter compatibilidade com código existente"""
    return get_constructor_standings('current')

# 4. Get driver cumulative points by race
@st.cache_data(ttl=600, show_spinner=False)
def get_driver_points_by_race(season: str = 'current') -> pd.DataFrame:
    """Obtém pontos acumulados dos pilotos por corrida
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    """
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/results.json?limit=2000")
    if not data:
        return _empty_df(['Round', 'Race'])

    try:
        all_races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return _empty_df(['Round', 'Race'])

    if not all_races:
        return _empty_df(['Round', 'Race'])

    unique_races = {}
    for race in all_races:
        round_num = _safe_int(race.get('round'), default=-1)
        if round_num > 0 and round_num not in unique_races:
            unique_races[round_num] = race

    rounds = sorted(unique_races.keys())
    if not rounds:
        return _empty_df(['Round', 'Race'])

    points_tracker: dict[str, dict[int, int]] = defaultdict(dict)
    driver_names: set[str] = set()

    for round_num in rounds:
        race = unique_races[round_num]
        for result in race.get('Results', []):
            driver_info = result.get('Driver', {})
            driver_name = f"{driver_info.get('givenName', '')} {driver_info.get('familyName', '')}".strip()
            if not driver_name:
                continue
            driver_names.add(driver_name)
            points_tracker[driver_name][round_num] = _safe_int(result.get('points'))

    output = {
        'Round': rounds,
        'Race': [str(unique_races[r].get('raceName', f'Round {r}')) for r in rounds],
    }

    for driver in sorted(driver_names):
        cumulative = 0
        cumulative_points = []
        for round_num in rounds:
            cumulative += points_tracker[driver].get(round_num, 0)
            cumulative_points.append(cumulative)
        output[driver] = cumulative_points

    return pd.DataFrame(output)

# 5. Get qualifying vs race position delta for last race
@st.cache_data(ttl=600, show_spinner=False)
def get_qualifying_vs_race_delta(season: str = 'current') -> pd.DataFrame:
    """Obtém diferença entre posição de classificatória e corrida (última prova da temporada)
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    """
    columns = ['Driver', 'Qualifying', 'Race', 'Delta']
    season_val = _resolve_season(season)
    race_resp_data = _request_json(f"{BASE_URL}/{season_val}/last.json")
    if not race_resp_data:
        return _empty_df(columns)

    try:
        races = race_resp_data['MRData']['RaceTable'].get('Races', [])
        round_num = str(races[0]['round']) if races else ""
    except (KeyError, TypeError, IndexError):
        return _empty_df(columns)

    if not round_num:
        return _empty_df(columns)

    race_data = _request_json(f"{BASE_URL}/{season_val}/{round_num}/results.json")
    qual_data = _request_json(f"{BASE_URL}/{season_val}/{round_num}/qualifying.json")
    if not race_data or not qual_data:
        return _empty_df(columns)

    try:
        race_races = race_data['MRData']['RaceTable'].get('Races', [])
        qual_races = qual_data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return _empty_df(columns)

    if not race_races or not qual_races:
        return _empty_df(columns)

    race_pos = {}
    for item in race_races[0].get('Results', []):
        driver = item.get('Driver', {})
        name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
        if name:
            race_pos[name] = _safe_int(item.get('position'))

    qual_pos = {}
    for item in qual_races[0].get('QualifyingResults', []):
        driver = item.get('Driver', {})
        name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
        if name:
            qual_pos[name] = _safe_int(item.get('position'))

    deltas = []
    for driver_name, qual_value in qual_pos.items():
        race_value = race_pos.get(driver_name)
        if race_value is None:
            continue
        deltas.append({
            'Driver': driver_name,
            'Qualifying': qual_value,
            'Race': race_value,
            'Delta': qual_value - race_value,
        })

    return pd.DataFrame(deltas, columns=columns)

# 6. Get fastest lap times from last race
@st.cache_data(ttl=600, show_spinner=False)
def get_fastest_lap_times(season: str = 'current') -> pd.DataFrame:
    """Obtém tempos de volta mais rápida da última corrida
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    """
    columns = ['Driver', 'Fastest Lap']
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/last/results.json")
    if not data:
        return _empty_df(columns)

    try:
        races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return _empty_df(columns)

    if not races:
        return _empty_df(columns)

    laps = []
    for item in races[0].get('Results', []):
        driver = item.get('Driver', {})
        fastest = item.get('FastestLap', {})
        fastest_time = fastest.get('Time', {}).get('time')
        if not fastest_time:
            continue
        name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
        laps.append({'Driver': name, 'Fastest Lap': fastest_time})

    return pd.DataFrame(laps, columns=columns)

# 7. Get pit stop data for the last race
@st.cache_data(ttl=600, show_spinner=False)
def get_pit_stop_data(season: str = 'current') -> pd.DataFrame:
    """Obtém dados de pit stops da última corrida
    
    Args:
        season: Ano da temporada (ex: '2024', '1950') ou 'current' para temporada atual
    
    Nota: Dados de pit stops estão disponíveis apenas a partir de 2011
    """
    columns = ['Driver', 'Lap', 'Stop', 'Time']
    season_val = _resolve_season(season)
    race_info = _request_json(f"{BASE_URL}/{season_val}/last.json")
    if not race_info:
        return _empty_df(columns)

    try:
        races = race_info['MRData']['RaceTable'].get('Races', [])
        round_num = str(races[0]['round']) if races else ""
    except (KeyError, TypeError, IndexError):
        return _empty_df(columns)

    if not round_num:
        return _empty_df(columns)

    data = _request_json(f"{BASE_URL}/{season_val}/{round_num}/pitstops.json?limit=1000")
    if not data:
        return _empty_df(columns)

    try:
        races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return _empty_df(columns)

    if not races:
        return _empty_df(columns)

    stops = races[0].get('PitStops', [])
    result = []
    for item in stops:
        result.append({
            "Driver": str(item.get('driverId', '')).capitalize(),
            "Lap": _safe_int(item.get('lap')),
            "Stop": _safe_int(item.get('stop')),
            "Time": str(item.get('duration', '')),
        })

    return pd.DataFrame(result, columns=columns)


@st.cache_data(ttl=3600, show_spinner=False)
def get_posicoes_recentes(season: str = 'current', n_corridas: int = 5) -> dict[str, list[int]]:
    """Retorna posições recentes por piloto: {nome_normalizado: [posições]}.

    Usa resultados oficiais da temporada e considera as últimas n corridas disponíveis.
    """
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/results.json?limit=2000")
    if not data:
        return {}

    try:
        races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return {}

    if not races:
        return {}

    unique_by_round: dict[int, dict] = {}
    for race in races:
        r = _safe_int(race.get('round'), default=-1)
        if r > 0 and r not in unique_by_round:
            unique_by_round[r] = race

    rounds = sorted(unique_by_round.keys())
    if not rounds:
        return {}

    selected_rounds = rounds[-max(1, int(n_corridas)):]
    out: dict[str, list[int]] = defaultdict(list)
    for rnd in selected_rounds:
        race = unique_by_round[rnd]
        for result in race.get('Results', []):
            driver = result.get('Driver', {})
            name = _normalize_driver_name(_extract_driver_name(driver))
            if not name:
                continue
            pos = _safe_int(result.get('position'), default=0)
            if pos > 0:
                out[name].append(pos)

    return dict(out)


@st.cache_data(ttl=3600, show_spinner=False)
def get_qualifying_grid_ultima_corrida(season: str = 'current') -> dict[str, int]:
    """Retorna grid de classificação da última corrida disponível na temporada.

    Formato: {nome_normalizado: posicao_grid}
    """
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/last/qualifying.json")
    if not data:
        return {}

    try:
        races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return {}

    if not races:
        return {}

    out: dict[str, int] = {}
    for item in races[0].get('QualifyingResults', []):
        driver = item.get('Driver', {})
        name = _normalize_driver_name(_extract_driver_name(driver))
        if not name:
            continue
        grid_pos = _safe_int(item.get('position'), default=0)
        if grid_pos > 0:
            out[name] = grid_pos
    return out


def _normalize_race_name(race_name: str) -> str:
    txt = str(race_name or "").strip().lower()
    txt = re.sub(r"grand prix|gp", "", txt)
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


@st.cache_data(ttl=3600, show_spinner=False)
def get_circuit_id_por_nome_prova(season: str, nome_prova: str) -> Optional[str]:
    """Resolve circuitId pelo vínculo direto salvo em `provas.circuit_id`."""
    season_val = _resolve_season(season)
    target = _normalize_race_name(nome_prova)
    if not target:
        return None

    try:
        from db.db_utils import db_connect

        with db_connect() as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info('provas')")
            cols = [r[1] for r in c.fetchall()]
            if 'circuit_id' not in cols or 'nome' not in cols:
                return None

            if 'temporada' in cols:
                c.execute(
                    """
                    SELECT nome, circuit_id
                    FROM provas
                    WHERE (temporada = ? OR temporada IS NULL)
                      AND circuit_id IS NOT NULL
                      AND TRIM(circuit_id) <> ''
                    """,
                    (season_val,),
                )
            else:
                c.execute(
                    """
                    SELECT nome, circuit_id
                    FROM provas
                    WHERE circuit_id IS NOT NULL
                      AND TRIM(circuit_id) <> ''
                    """
                )

            rows = c.fetchall() or []
            for prova_nome, circuit_id in rows:
                if _normalize_race_name(str(prova_nome)) == target:
                    return str(circuit_id)
    except Exception:
        return None

    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_historico_circuito(circuit_id: str, n_anos: int = 4, season_ref: str = 'current') -> dict[str, float]:
    """Retorna média de posição no circuito: {nome_normalizado: media_posicao}."""
    if not circuit_id:
        return {}

    season_val = _resolve_season(season_ref)
    ano_ref = _safe_int(season_val, default=datetime.datetime.now().year)
    anos = [str(ano) for ano in range(max(1950, ano_ref - max(1, n_anos) + 1), ano_ref + 1)]

    acum: dict[str, list[int]] = defaultdict(list)
    for ano in anos:
        data = _request_json(f"{BASE_URL}/{ano}/circuits/{circuit_id}/results.json?limit=2000")
        if not data:
            continue
        try:
            races = data['MRData']['RaceTable'].get('Races', [])
        except (KeyError, TypeError):
            continue
        for race in races:
            for result in race.get('Results', []):
                driver = result.get('Driver', {})
                name = _normalize_driver_name(_extract_driver_name(driver))
                if not name:
                    continue
                pos = _safe_int(result.get('position'), default=0)
                if pos > 0:
                    acum[name].append(pos)

    medias: dict[str, float] = {}
    for name, posicoes in acum.items():
        if posicoes:
            medias[name] = float(sum(posicoes)) / float(len(posicoes))
    return medias


@st.cache_data(ttl=86400, show_spinner=False)
def get_frequencia_11_por_piloto(seasons: Optional[list[str]] = None) -> dict[str, float]:
    """Retorna frequência relativa em P11 por piloto para as temporadas informadas.

    Formato: {nome_normalizado: frequencia_0_a_1}
    """
    if not seasons:
        current = _safe_int(get_current_season(), default=datetime.datetime.now().year)
        seasons = [str(current - 2), str(current - 1), str(current)]

    total_corridas = 0
    contagem_p11: dict[str, int] = defaultdict(int)

    for season in seasons:
        season_val = _resolve_season(str(season))
        season_results = _request_json(f"{BASE_URL}/{season_val}/results.json?limit=2000")
        if season_results:
            try:
                races_all = season_results['MRData']['RaceTable'].get('Races', [])
                total_corridas += len(races_all)
            except (KeyError, TypeError):
                pass

        data = _request_json(f"{BASE_URL}/{season_val}/results/11.json?limit=2000")
        if not data:
            continue
        try:
            races = data['MRData']['RaceTable'].get('Races', [])
        except (KeyError, TypeError):
            continue

        for race in races:
            results = race.get('Results', [])
            if not results:
                continue
            driver = results[0].get('Driver', {})
            name = _normalize_driver_name(_extract_driver_name(driver))
            if name:
                contagem_p11[name] += 1

    if total_corridas <= 0:
        return {}

    return {name: (count / float(total_corridas)) for name, count in contagem_p11.items()}


@st.cache_data(ttl=3600, show_spinner=False)
def get_taxa_dnf_por_piloto(
    season: str = 'current',
    n_corridas: int = 8,
    usar_suavizacao: bool = True,
    prior_corridas: int = 4,
    prior_taxa_dnf: float = 0.18,
) -> dict[str, float]:
    """Retorna taxa de DNF recente por piloto: {nome_normalizado: taxa_0_a_1}.

    Quando usar_suavizacao=True, aplica prior bayesiano para reduzir extremos no início da temporada:
      taxa = (dnf_observado + prior_corridas * prior_taxa_dnf) / (corridas_observadas + prior_corridas)
    """
    season_val = _resolve_season(season)
    data = _request_json(f"{BASE_URL}/{season_val}/results.json?limit=2000")
    if not data:
        return {}

    try:
        races = data['MRData']['RaceTable'].get('Races', [])
    except (KeyError, TypeError):
        return {}

    if not races:
        return {}

    unique_by_round: dict[int, dict] = {}
    for race in races:
        r = _safe_int(race.get('round'), default=-1)
        if r > 0 and r not in unique_by_round:
            unique_by_round[r] = race
    rounds = sorted(unique_by_round.keys())
    if not rounds:
        return {}

    selected_rounds = rounds[-max(1, int(n_corridas)):]
    total_partidas: dict[str, int] = defaultdict(int)
    total_dnf: dict[str, int] = defaultdict(int)

    for rnd in selected_rounds:
        race = unique_by_round[rnd]
        for result in race.get('Results', []):
            driver = result.get('Driver', {})
            name = _normalize_driver_name(_extract_driver_name(driver))
            if not name:
                continue
            total_partidas[name] += 1
            status = str(result.get('status', ''))
            if not _status_is_finished(status):
                total_dnf[name] += 1

    out: dict[str, float] = {}
    for name, total in total_partidas.items():
        if total > 0:
            dnf_obs = float(total_dnf.get(name, 0))
            if usar_suavizacao and prior_corridas > 0:
                prior_taxa = max(0.0, min(1.0, float(prior_taxa_dnf)))
                numerador = dnf_obs + (float(prior_corridas) * prior_taxa)
                denominador = float(total) + float(prior_corridas)
                out[name] = numerador / denominador
            else:
                out[name] = dnf_obs / float(total)
    return out
