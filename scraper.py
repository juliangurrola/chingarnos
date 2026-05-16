import requests
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from database import get_connection

def fetch_daily_schedule(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
        
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher,venue,weather"
    response = requests.get(url)
    
    if response.status_code != 200:
        print("Error fetching MLB schedule")
        return
        
    data = response.json()
    dates = data.get('dates', [])
    if not dates:
        print(f"No games found for {date_str}")
        return
        
    games = dates[0].get('games', [])
    
    conn = get_connection()
    cursor = conn.cursor()
    
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
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_schedule 
            (game_id, game_date, home_team, away_team, venue_name, weather_condition, 
             temperature, wind_speed, wind_direction, home_pitcher_id, home_pitcher_name, 
             away_pitcher_id, away_pitcher_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, date_str, home_team, away_team, venue_name, weather_cond,
              temp, wind_speed, wind_direction, home_pitcher_id, home_pitcher_name,
              away_pitcher_id, away_pitcher_name, status))
              
    conn.commit()
    conn.close()
    print(f"✅ Descargados {len(games)} partidos para la fecha {date_str}")

if __name__ == "__main__":
    fetch_daily_schedule()
