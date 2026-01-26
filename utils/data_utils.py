import requests
import pandas as pd
from collections import defaultdict

BASE_URL = "https://api.jolpi.ca/ergast/f1"

# 1. Get current F1 season
def get_current_season():
    """Obtém a temporada atual da F1"""
    try:
        url = f"{BASE_URL}/current.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        season = data['MRData']['RaceTable']['season']
        return season
    except Exception as e:
        # Fallback para ano atual
        import datetime
        return str(datetime.datetime.now().year)

# 2. Get current driver standings
def get_current_driver_standings():
    """Obtém classificação atual de pilotos"""
    try:
        url = f"{BASE_URL}/current/driverStandings.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        standings_lists = data['MRData']['StandingsTable'].get('StandingsLists', [])
        
        # Verifica se há dados disponíveis
        if not standings_lists or len(standings_lists) == 0:
            # Retorna DataFrame vazio com estrutura correta
            return pd.DataFrame(columns=['Position', 'Driver', 'Points', 'Wins', 'Nationality', 'Constructor'])
        
        standings = standings_lists[0].get('DriverStandings', [])
        
        if not standings:
            return pd.DataFrame(columns=['Position', 'Driver', 'Points', 'Wins', 'Nationality', 'Constructor'])
        
        drivers = []
        for s in standings:
            driver = s['Driver']
            constructor = s['Constructors'][0] if s.get('Constructors') else {'name': 'N/A'}
            drivers.append({
                'Position': int(s['position']),
                'Driver': f"{driver['givenName']} {driver['familyName']}",
                'Points': int(float(s['points'])),
                'Wins': int(s['wins']),
                'Nationality': driver['nationality'],
                'Constructor': constructor['name']
            })
            
        return pd.DataFrame(drivers)
        
    except Exception as e:
        # Em caso de erro, retorna DataFrame vazio
        return pd.DataFrame(columns=['Position', 'Driver', 'Points', 'Wins', 'Nationality', 'Constructor'])

# 3. Get current constructor standings
def get_current_constructor_standings():
    """Obtém classificação atual de construtores"""
    try:
        url = f"{BASE_URL}/current/constructorStandings.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        standings_lists = data['MRData']['StandingsTable'].get('StandingsLists', [])
        
        if not standings_lists or len(standings_lists) == 0:
            return pd.DataFrame(columns=['Position', 'Constructor', 'Points', 'Wins', 'Nationality'])
        
        standings = standings_lists[0].get('ConstructorStandings', [])
        
        if not standings:
            return pd.DataFrame(columns=['Position', 'Constructor', 'Points', 'Wins', 'Nationality'])
        
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
        
    except Exception as e:
        return pd.DataFrame(columns=['Position', 'Constructor', 'Points', 'Wins', 'Nationality'])

# 4. Get driver cumulative points by race
def get_driver_points_by_race(season='current'):
    """Obtém pontos acumulados dos pilotos por corrida"""
    try:
        # Determinar a temporada atual se necessário
        if season == 'current':
            response = requests.get(f"{BASE_URL}/current.json", timeout=10)
            response.raise_for_status()
            data = response.json()
            season = data['MRData']['RaceTable']['season']
        
        # Gerar lista de offsets (0 até 720 em incrementos de 30)
        offsets = list(range(0, 721, 30))
        all_races = []
        
        # Coletar dados de todos os offsets
        for offset in offsets:
            url = f"{BASE_URL}/{season}/results.json?limit=720&offset={offset}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            races = data['MRData']['RaceTable'].get('Races', [])
            
            if not races:
                break
                
            all_races.extend(races)
        
        if not all_races:
            return pd.DataFrame(columns=['Round', 'Race'])
        
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
            
            for result in race.get('Results', []):
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
        
    except Exception as e:
        return pd.DataFrame(columns=['Round', 'Race'])

# 5. Get qualifying vs race position delta for last race
def get_qualifying_vs_race_delta():
    """Obtém diferença entre posição de classificatória e corrida"""
    try:
        last_race_url = f"{BASE_URL}/current/last.json"
        race_resp = requests.get(last_race_url, timeout=10)
        race_resp.raise_for_status()
        race_resp_data = race_resp.json()
        
        races = race_resp_data['MRData']['RaceTable'].get('Races', [])
        if not races:
            return pd.DataFrame(columns=['Driver', 'Qualifying', 'Race', 'Delta'])
        
        round_num = races[0]['round']

        race_results_url = f"{BASE_URL}/current/{round_num}/results.json"
        qual_results_url = f"{BASE_URL}/current/{round_num}/qualifying.json"

        race_data = requests.get(race_results_url, timeout=10).json()
        qual_data = requests.get(qual_results_url, timeout=10).json()
        
        race_races = race_data['MRData']['RaceTable'].get('Races', [])
        qual_races = qual_data['MRData']['RaceTable'].get('Races', [])
        
        if not race_races or not qual_races:
            return pd.DataFrame(columns=['Driver', 'Qualifying', 'Race', 'Delta'])

        race_pos = {}
        for res in race_races[0].get('Results', []):
            name = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
            race_pos[name] = int(res['position'])

        qual_pos = {}
        for res in qual_races[0].get('QualifyingResults', []):
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
        
    except Exception as e:
        return pd.DataFrame(columns=['Driver', 'Qualifying', 'Race', 'Delta'])

# 6. Get fastest lap times from last race
def get_fastest_lap_times():
    """Obtém tempos de volta mais rápida da última corrida"""
    try:
        url = f"{BASE_URL}/current/last/results.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        races = data['MRData']['RaceTable'].get('Races', [])
        if not races:
            return pd.DataFrame(columns=['Driver', 'Fastest Lap'])

        laps = []
        for res in races[0].get('Results', []):
            driver = res['Driver']
            name = f"{driver['givenName']} {driver['familyName']}"
            if 'FastestLap' in res and 'Time' in res['FastestLap']:
                time = res['FastestLap']['Time']['time']
                laps.append({'Driver': name, 'Fastest Lap': time})

        return pd.DataFrame(laps)
        
    except Exception as e:
        return pd.DataFrame(columns=['Driver', 'Fastest Lap'])

# 7. Get pit stop data for the last race
def get_pit_stop_data():
    """Obtém dados de pit stops da última corrida"""
    try:
        race_info_resp = requests.get(f"{BASE_URL}/current/last.json", timeout=10)
        race_info_resp.raise_for_status()
        race_info = race_info_resp.json()
        
        races = race_info['MRData']['RaceTable'].get('Races', [])
        if not races:
            return pd.DataFrame(columns=['Driver', 'Lap', 'Stop', 'Time'])
        
        round_num = races[0]['round']

        url = f"{BASE_URL}/current/{round_num}/pitstops.json?limit=1000"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        races = data['MRData']['RaceTable'].get('Races', [])
        if not races:
            return pd.DataFrame(columns=['Driver', 'Lap', 'Stop', 'Time'])

        stops = races[0].get('PitStops', [])
        result = [{
            "Driver": s['driverId'].capitalize(),
            "Lap": int(s['lap']),
            "Stop": int(s['stop']),
            "Time": s['duration']
        } for s in stops]

        return pd.DataFrame(result)
        
    except Exception as e:
        return pd.DataFrame(columns=['Driver', 'Lap', 'Stop', 'Time'])
