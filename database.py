import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'mlb_stats.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla del calendario diario y clima
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_schedule (
            game_id INTEGER PRIMARY KEY,
            game_date TEXT,
            home_team TEXT,
            away_team TEXT,
            venue_name TEXT,
            weather_condition TEXT,
            temperature INTEGER,
            wind_speed TEXT,
            wind_direction TEXT,
            home_pitcher_id INTEGER,
            home_pitcher_name TEXT,
            away_pitcher_id INTEGER,
            away_pitcher_name TEXT,
            status TEXT
        )
    ''')
    
    # Tabla de predicciones y apuestas sugeridas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            game_id INTEGER PRIMARY KEY,
            home_win_prob REAL,
            away_win_prob REAL,
            expected_total_runs REAL,
            suggested_bet TEXT,
            confidence_score REAL,
            key_insight TEXT,
            FOREIGN KEY (game_id) REFERENCES daily_schedule (game_id)
        )
    ''')
    
    # Tabla temporal de stats de pitchers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pitcher_stats (
            player_id INTEGER PRIMARY KEY,
            name TEXT,
            era REAL,
            whip REAL,
            strikeout_rate REAL,
            walk_rate REAL,
            last_updated TEXT
        )
    ''')
    
    # Tabla temporal de stats de bateo del equipo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_batting_stats (
            team_name TEXT PRIMARY KEY,
            ops_vs_rhp REAL,
            ops_vs_lhp REAL,
            woba REAL,
            runs_per_game REAL,
            last_updated TEXT
        )
    ''')
    
    # NUEVO: Tabla de Props de Jugadores (Strikeouts, etc)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_props (
            prop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            player_name TEXT,
            player_id INTEGER,
            prop_type TEXT,
            line REAL,
            suggested_side TEXT,
            american_odds TEXT,
            confidence_score REAL,
            key_insight TEXT,
            FOREIGN KEY(game_id) REFERENCES daily_schedule(game_id)
        )
    ''')
    
    # NUEVO: Tabla de Parlays Sugeridos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_parlays (
            parlay_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parlay_name TEXT,
            legs_description TEXT,
            combined_american_odds TEXT,
            win_probability REAL
        )
    ''')
    
    # Intento de agregar columna key_insight si ya existía la tabla vieja
    try:
        cursor.execute('ALTER TABLE predictions ADD COLUMN key_insight TEXT')
    except sqlite3.OperationalError: pass

    try:
        cursor.execute('ALTER TABLE player_props ADD COLUMN player_id INTEGER')
    except sqlite3.OperationalError: pass
        
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente.")

if __name__ == '__main__':
    init_db()
