import requests
import pandas as pd

BASE_URL = "https://api.jolpi.ca/ergast/f1"

# 1. Get current F1 season
def get_current_season():
    url = f"{BASE_URL}/current.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    season = data['MRData']['RaceTable']['season']
    return season

# 2. Get current driver standings
def get_current_driver_standings():
    url = f"{BASE_URL}/current/driverStandings.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    standings = data['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']
    
    drivers = []
    for s in standings:
        driver = s['Driver']
        constructor = s['Constructors'][0]
        drivers.append({
            'Position': int(s['position']),
            'Driver': f"{driver['givenName']} {driver['familyName']}",
            'Points': int(float(s['points'])),
            'Wins': int(s['wins']),
            'Nationality': driver['nationality'],
            'Constructor': constructor['name']
        })
        
    return pd.DataFrame(drivers)

# 3. Get current constructor standings
def get_current_constructor_standings():
    url = f"{BASE_URL}/current/constructorStandings.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    standings = data['MRData']['StandingsTable']['StandingsLists'][0]['ConstructorStandings']
    
    constructors = []
    for s in standings:
        constructor = s['Constructor']
        constructors.append({
            'Position': int(s['position']),
            'Constructor': constructor['name'],
            'Points': int(float(s['points'])),
            'Wins': int(s['wins']),
            'Nationality': constructor['nationality']
        })
        
    return pd.DataFrame(constructors)

# 4. Get driver cumulative points by race
import requests
import pandas as pd
from collections import defaultdict

BASE_URL = "https://api.jolpi.ca/ergast/f1"

def get_driver_points_by_race(season='current'):
    # Determinar a temporada atual se necessário
    if season == 'current':
        response = requests.get(f"{BASE_URL}/current.json")
        response.raise_for_status()
        data = response.json()
        season = data['MRData']['RaceTable']['season']
    
    # Gerar lista de offsets (0 até 720 em incrementos de 30)
    offsets = list(range(0, 721, 30))
    all_races = []
    
    # Coletar dados de todos os offsets
    for offset in offsets:
        url = f"{BASE_URL}/{season}/results.json?limit=720&offset={offset}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        races = data['MRData']['RaceTable']['Races']
        
        if not races:
            break
            
        all_races.extend(races)
    
    # Remover duplicatas usando o número da rodada
    unique_races = {}
    for race in all_races:
        round_num = int(race['round'])
        if round_num not in unique_races:
            unique_races[round_num] = race
    
    # Ordenar corridas pelo número da rodada
    sorted_rounds = sorted(unique_races.keys())
    races_sorted = [unique_races[round_num] for round_num in sorted_rounds]
    
    # Rastrear pontos por piloto
    points_tracker = defaultdict(dict)
    driver_names = set()
    
    for race in races_sorted:
        round_num = int(race['round'])
        race_name = race['raceName']
        
        for result in race['Results']:
            driver_name = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
            driver_names.add(driver_name)
            
            try:
                points = int(float(result['points']))
            except (ValueError, TypeError):
                points = 0
                
            points_tracker[driver_name][round_num] = points
    
    # Preparar dados para o DataFrame
    rounds = sorted_rounds
    race_names = [unique_races[r]['raceName'] for r in rounds]
    
    data = {'Round': rounds, 'Race': race_names}
    
    for driver in driver_names:
        cumulative_points = []
        cumulative = 0
        
        for round_num in rounds:
            points = points_tracker[driver].get(round_num, 0)
            cumulative += points
            cumulative_points.append(cumulative)
        
        data[driver] = cumulative_points
    
    return pd.DataFrame(data)

# 5. Get qualifying vs race position delta for last race
def get_qualifying_vs_race_delta():
    last_race_url = f"{BASE_URL}/current/last.json"
    race_resp = requests.get(last_race_url).json()
    round_num = race_resp['MRData']['RaceTable']['round']

    race_results_url = f"{BASE_URL}/current/{round_num}/results.json"
    qual_results_url = f"{BASE_URL}/current/{round_num}/qualifying.json"

    race_data = requests.get(race_results_url).json()
    qual_data = requests.get(qual_results_url).json()

    race_pos = {}
    for res in race_data['MRData']['RaceTable']['Races'][0]['Results']:
        name = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
        race_pos[name] = int(res['position'])

    qual_pos = {}
    for res in qual_data['MRData']['RaceTable']['Races'][0]['QualifyingResults']:
        name = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
        qual_pos[name] = int(res['position'])

    deltas = []
    for driver in qual_pos:
        if driver in race_pos:
            deltas.append({
                'Driver': driver,
                'Qualifying': qual_pos[driver],
                'Race': race_pos[driver],
                'Delta': qual_pos[driver] - race_pos[driver]
            })

    return pd.DataFrame(deltas)

# 6. Get fastest lap times from last race
def get_fastest_lap_times():
    url = f"{BASE_URL}/current/last/results.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    laps = []
    for res in data['MRData']['RaceTable']['Races'][0]['Results']:
        driver = res['Driver']
        name = f"{driver['givenName']} {driver['familyName']}"
        if 'FastestLap' in res:
            time = res['FastestLap']['Time']['time']
            laps.append({'Driver': name, 'Fastest Lap': time})

    return pd.DataFrame(laps)

# 7. Get pit stop data for the last race
def get_pit_stop_data():
    race_info = requests.get(f"{BASE_URL}/current/last.json").json()
    round_num = race_info['MRData']['RaceTable']['round']

    url = f"{BASE_URL}/current/{round_num}/pitstops.json?limit=1000"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    stops = data['MRData']['RaceTable']['Races'][0].get('PitStops', [])
    result = [{
        "Driver": s['driverId'].capitalize(),
        "Lap": int(s['lap']),
        "Stop": int(s['stop']),
        "Time": s['duration']
    } for s in stops]

    return pd.DataFrame(result)
