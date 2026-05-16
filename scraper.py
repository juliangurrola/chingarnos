import requests
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from database import get_connection

def fetch_pitcher_stats(pitcher_id):
    if pitcher_id == 0: return None
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats?stats=season&group=pitching"
    try:
        res = requests.get(url).json()
        stats = res['stats'][0]['splits'][0]['stat']
        return {
            'era': stats.get('era', '0.00'),
            'whip': stats.get('whip', '0.00'),
            'k9': stats.get('strikeOutsPer9Inn', '0.0')
        }
    except: return None

def fetch_team_stats(team_id):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&group=hitting"
    try:
        res = requests.get(url).json()
        stats = res['stats'][0]['splits'][0]['stat']
        return {
            'avg': stats.get('avg', '.000'),
            'ops': stats.get('ops', '.000'),
            'rpg': stats.get('runsPerGame', '0.0')
        }
    except: return None

def fetch_daily_schedule():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    dates_to_fetch = [today.strftime('%Y-%m-%d'), tomorrow.strftime('%Y-%m-%d')]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Limpiar solo juegos futuros para no duplicar si se corre varias veces
    cursor.execute("DELETE FROM daily_schedule")
    
    total_games = 0
    for date_str in dates_to_fetch:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher,venue,weather"
        response = requests.get(url)
        
        if response.status_code != 200: continue
            
        data = response.json()
        dates = data.get('dates', [])
        if not dates: continue
            
        games = dates[0].get('games', [])
        total_games += len(games)
    
        for game in games:
            game_id = game['gamePk']
            status = game['status']['detailedState']
            
            home_team = game['teams']['home']['team']['name']
            away_team = game['teams']['away']['team']['name']
            
            venue_name = game.get('venue', {}).get('name', 'Unknown')
            
            weather = game.get('weather', {})
            weather_cond = weather.get('condition', 'Unknown')
            temp = weather.get('temp', 0)
            wind = weather.get('wind', '0 mph')
            
            # Parse wind (e.g. "10 mph, Out To CF")
            wind_speed = '0'
            wind_direction = 'Unknown'
            if wind and wind != '0 mph':
                parts = wind.split(', ')
                if len(parts) > 0:
                    wind_speed = parts[0].replace(' mph', '')
                if len(parts) > 1:
                    wind_direction = parts[1]
                    
            # Pitchers
            home_pitcher = game['teams']['home'].get('probablePitcher', {})
            home_pitcher_id = home_pitcher.get('id', 0)
            home_pitcher_name = home_pitcher.get('fullName', 'Unknown')
            
            away_pitcher = game['teams']['away'].get('probablePitcher', {})
            away_pitcher_id = away_pitcher.get('id', 0)
            away_pitcher_name = away_pitcher.get('fullName', 'Unknown')

            # OBTENER LINEUP/BATEADORES (Nuevos datos)
            try:
                roster_url = f"https://statsapi.mlb.com/api/v1/teams/{home_id}/roster"
                r_data = requests.get(roster_url).json()
                # Tomamos los primeros 5 bateadores destacados
                for p in r_data.get('roster', [])[:5]:
                    p_name = p['person']['fullName']
                    p_id = p['person']['id']
                    if p['position']['type'] != 'Pitcher':
                        cursor.execute('INSERT OR REPLACE INTO player_props (game_id, player_name, player_id, prop_type) VALUES (?, ?, ?, ?)',
                                       (game_id, p_name, p_id, "Bateador"))
            except: pass
            
            cursor.execute('''
                INSERT OR REPLACE INTO daily_schedule 
                (game_id, game_date, home_team, away_team, venue_name, weather_condition, 
                 temperature, wind_speed, wind_direction, home_pitcher_id, home_pitcher_name, 
                 away_pitcher_id, away_pitcher_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (game_id, date_str, home_team, away_team, venue_name, weather_cond,
                  temp, wind_speed, wind_direction, home_pitcher_id, home_pitcher_name,
                  away_pitcher_id, away_pitcher_name, status))

            # --- JALAR STATS REALES DE LA WEB ---
            h_stats = fetch_pitcher_stats(home_pitcher_id)
            if h_stats:
                cursor.execute('''INSERT OR REPLACE INTO pitcher_stats (player_id, name, era, whip, strikeout_rate, last_updated)
                                  VALUES (?, ?, ?, ?, ?, ?)''', 
                               (home_pitcher_id, home_pitcher_name, h_stats['era'], h_stats['whip'], h_stats['k9'], date_str))
            
            a_stats = fetch_pitcher_stats(away_pitcher_id)
            if a_stats:
                cursor.execute('''INSERT OR REPLACE INTO pitcher_stats (player_id, name, era, whip, strikeout_rate, last_updated)
                                  VALUES (?, ?, ?, ?, ?, ?)''', 
                               (away_pitcher_id, away_pitcher_name, a_stats['era'], a_stats['whip'], a_stats['k9'], date_str))

            # Stats de Equipos
            home_team_id = game['teams']['home']['team']['id']
            away_team_id = game['teams']['away']['team']['id']
            
            h_team_stats = fetch_team_stats(home_team_id)
            if h_team_stats:
                cursor.execute('''INSERT OR REPLACE INTO team_batting_stats (team_name, ops_vs_rhp, runs_per_game, last_updated)
                                  VALUES (?, ?, ?, ?)''',
                               (home_team, h_team_stats['ops'], h_team_stats['rpg'], date_str))
            
            a_team_stats = fetch_team_stats(away_team_id)
            if a_team_stats:
                cursor.execute('''INSERT OR REPLACE INTO team_batting_stats (team_name, ops_vs_rhp, runs_per_game, last_updated)
                                  VALUES (?, ?, ?, ?)''',
                               (away_team, a_team_stats['ops'], a_team_stats['rpg'], date_str))

              
    conn.commit()
    conn.close()
    print(f"✅ Descargados {total_games} partidos de hoy y mañana.")

if __name__ == "__main__":
    fetch_daily_schedule()
