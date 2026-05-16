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

def fetch_mlb_news():
    import xml.etree.ElementTree as ET
    url = "https://news.google.com/rss/search?q=MLB+highlights+news&hl=es-419&gl=MX&ceid=MX:es-419"
    try:
        res = requests.get(url)
        root = ET.fromstring(res.content)
        news = []
        for item in root.findall('.//item')[:10]:
            news.append({
                "title": item.find('title').text,
                "link": item.find('link').text,
                "summary": "Titular de tendencia global en el mundo del béisbol.",
                "date": item.find('pubDate').text[:16]
            })
        return news
    except Exception as e:
        print(f"Error en noticias: {e}")
        return []

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
    
        for g in games:
            g_id = g['gamePk']
            h_team_data = g.get('teams', {}).get('home', {}).get('team', {})
            h_team = h_team_data.get('name', 'N/A')
            h_team_id = h_team_data.get('id', 0)
            
            a_team_data = g.get('teams', {}).get('away', {}).get('team', {})
            a_team = a_team_data.get('name', 'N/A')
            a_team_id = a_team_data.get('id', 0)
            
            venue = g.get('venue', {}).get('name', 'N/A')
            status = g.get('status', {}).get('detailedState', 'N/A')
            
            # Datos del clima
            weather = g.get('weather', {})
            cond = weather.get('condition', 'Despejado')
            temp = weather.get('temp', '--')
            wind_raw = weather.get('wind', 'Pendiente')
            w_speed = "0"; w_dir = "Calma"
            if wind_raw != 'Pendiente' and ' ' in wind_raw:
                parts = wind_raw.split(', ')
                w_speed = parts[0].replace(' mph', '')
                w_dir = parts[1] if len(parts) > 1 else "Variable"
            
            # Pitchers
            h_pitcher = g.get('teams', {}).get('home', {}).get('probablePitcher', {})
            h_p_name = h_pitcher.get('fullName', 'Unknown')
            h_p_id = h_pitcher.get('id', 0)
            
            a_pitcher = g.get('teams', {}).get('away', {}).get('probablePitcher', {})
            a_p_name = a_pitcher.get('fullName', 'Unknown')
            a_p_id = a_pitcher.get('id', 0)

            # OBTENER ROSTERS REALES (HOME Y AWAY)
            for t_id in [h_team_id, a_team_id]:
                try:
                    r_url = f"https://statsapi.mlb.com/api/v1/teams/{t_id}/roster"
                    r_data = requests.get(r_url).json()
                    for p in r_data.get('roster', []):
                        p_name = p['person']['fullName']
                        p_id = p['person']['id']
                        if p['position']['type'] != 'Pitcher' and p_id > 0:
                            cursor.execute('INSERT OR REPLACE INTO player_props (game_id, player_name, player_id, team_id, prop_type) VALUES (?, ?, ?, ?, ?)',
                                           (g_id, p_name, p_id, t_id, "Bateador"))
                except: pass
            
            cursor.execute('''
                INSERT OR REPLACE INTO daily_schedule 
                (game_id, game_date, home_team, home_team_id, away_team, away_team_id, venue_name, weather_condition, 
                 temperature, wind_speed, wind_direction, home_pitcher_id, home_pitcher_name, 
                 away_pitcher_id, away_pitcher_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (g_id, date_str, h_team, h_team_id, a_team, a_team_id, venue, cond,
                  temp, w_speed, w_dir, h_p_id, h_p_name, a_p_id, a_p_name, status))

            # Stats de Pitchers
            h_stats = fetch_pitcher_stats(h_p_id)
            if h_stats:
                cursor.execute('INSERT OR REPLACE INTO pitcher_stats (player_id, name, era, whip, strikeout_rate, last_updated) VALUES (?, ?, ?, ?, ?, ?)', 
                               (h_p_id, h_p_name, h_stats['era'], h_stats['whip'], h_stats['k9'], date_str))
            
            a_stats = fetch_pitcher_stats(a_p_id)
            if a_stats:
                cursor.execute('INSERT OR REPLACE INTO pitcher_stats (player_id, name, era, whip, strikeout_rate, last_updated) VALUES (?, ?, ?, ?, ?, ?)', 
                               (a_p_id, a_p_name, a_stats['era'], a_stats['whip'], a_stats['k9'], date_str))

            # Stats de Equipos
            h_team_stats = fetch_team_stats(h_team_id)
            if h_team_stats:
                cursor.execute('INSERT OR REPLACE INTO team_batting_stats (team_name, ops_vs_rhp, runs_per_game, last_updated) VALUES (?, ?, ?, ?)',
                               (h_team, h_team_stats['ops'], h_team_stats['rpg'], date_str))
            
            a_team_stats = fetch_team_stats(a_team_id)
            if a_team_stats:
                cursor.execute('INSERT OR REPLACE INTO team_batting_stats (team_name, ops_vs_rhp, runs_per_game, last_updated) VALUES (?, ?, ?, ?)',
                               (a_team, a_team_stats['ops'], a_team_stats['rpg'], date_str))

              
    # --- NOTICIAS Y TENDENCIAS ---
    cursor.execute("DELETE FROM mlb_news")
    news_items = fetch_mlb_news()
    for item in news_items:
        cursor.execute('INSERT INTO mlb_news (title, link, summary, published) VALUES (?, ?, ?, ?)',
                       (item['title'], item['link'], item['summary'], item['date']))
              
    conn.commit()
    conn.close()
    print(f"✅ Descargados {total_games} partidos y noticias de hoy.")

if __name__ == "__main__":
    fetch_daily_schedule()
