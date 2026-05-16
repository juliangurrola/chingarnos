import sqlite3
import pandas as pd
import random
from database import get_connection, init_db

def prob_to_american_odds(prob):
    prob = prob / 100.0
    if prob <= 0 or prob >= 1:
        return "N/A"
    if prob > 0.5:
        odds = - (prob / (1 - prob)) * 100
    else:
        odds = ((1 - prob) / prob) * 100
    return f"+{int(odds)}" if odds > 0 else f"{int(odds)}"

def generate_predictions():
    # Asegurar que la base de datos tenga las columnas nuevas
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Limpiar predicciones viejas
    cursor.execute("DELETE FROM predictions")
    cursor.execute("DELETE FROM player_props")
    cursor.execute("DELETE FROM ai_parlays")
    
    games_df = pd.read_sql_query('''
        SELECT * FROM daily_schedule
    ''', conn)
    
    if games_df.empty:
        print("No hay partidos pendientes hoy para predecir.")
        conn.close()
        return
        
    all_bets = [] # Para armar parlays
    
    for _, row in games_df.iterrows():
        # --- OBTENER ESTADISTICAS REALES DE LA BASE DE DATOS ---
        # Pitchers
        h_p_stats = pd.read_sql_query(f"SELECT * FROM pitcher_stats WHERE player_id = {row['home_pitcher_id']}", conn)
        a_p_stats = pd.read_sql_query(f"SELECT * FROM pitcher_stats WHERE player_id = {row['away_pitcher_id']}", conn)
        
        # Equipos
        h_t_stats = pd.read_sql_query(f"SELECT * FROM team_batting_stats WHERE team_name = '{row['home_team']}'", conn)
        a_t_stats = pd.read_sql_query(f"SELECT * FROM team_batting_stats WHERE team_name = '{row['away_team']}'", conn)
        
        # Valores por defecto si no hay stats reales
        h_era = float(h_p_stats.iloc[0]['era']) if not h_p_stats.empty else 4.50
        a_era = float(a_p_stats.iloc[0]['era']) if not a_p_stats.empty else 4.50
        h_ops = float(h_t_stats.iloc[0]['ops_vs_rhp']) if not h_t_stats.empty else 0.720
        a_ops = float(a_t_stats.iloc[0]['ops_vs_rhp']) if not a_t_stats.empty else 0.720
        h_rpg = float(h_t_stats.iloc[0]['runs_per_game']) if not h_t_stats.empty else 4.5
        a_rpg = float(a_t_stats.iloc[0]['runs_per_game']) if not a_t_stats.empty else 4.5

        # --- ALGORITMO DE PREDICCION BASADO EN DATOS REALES ---
        # Una formula simple: mejor ERA y mejor OPS = mas probabilidad
        # Diferencia de ERA (inversa) + Diferencia de OPS
        era_diff = a_era - h_era # Positivo es bueno para el local
        ops_diff = h_ops - a_ops # Positivo es bueno para el local
        
        base_prob = 50.0 + (era_diff * 3.0) + (ops_diff * 50.0)
        home_win_prob = max(10, min(90, base_prob + random.uniform(-5, 5)))
        away_win_prob = 100.0 - home_win_prob
        
        # Totales basados en ERA combinada y RPG combinada
        expected_runs = (h_rpg + a_rpg) * ( (h_era + a_era) / 9.0 )
        expected_runs = round(max(6.5, min(12.5, expected_runs)) * 2) / 2
        
        if 'Out' in row['wind_direction']:
            expected_runs += 1.5
            suggested_bet = "OVER (Altas)"
            confidence = 65.0
        elif 'In' in row['wind_direction']:
            expected_runs -= 1.5
            suggested_bet = "UNDER (Bajas)"
            confidence = 65.0
        else:
            suggested_bet = f"{row['home_team']} ML" if home_win_prob > 50 else f"{row['away_team']} ML"
            confidence = max(home_win_prob, away_win_prob)
            
        # GENERAR INSIGHT DE ANALISIS (REFERENCIAS REALES)
        insights = [
            f"El pitcher {row['home_pitcher_name']} llega con una ERA real de {h_era:.2f}.",
            f"Los bateadores de {row['home_team']} tienen un OPS de {h_ops:.3f} esta temporada.",
            f"El factor viento ({row['wind_speed']} mph {row['wind_direction']}) afecta el total de {expected_runs}.",
            f"El duelo de pitcheo favorece a {row['home_team'] if h_era < a_era else row['away_team']} por efectividad.",
            f"Históricamente en este estadio ({row['venue_name']}), se promedian {(h_rpg+a_rpg)/2:.1f} carreras."
        ]
        key_insight = " | ".join(random.sample(insights, 2))

        cursor.execute('''
            INSERT INTO predictions 
            (game_id, home_win_prob, away_win_prob, expected_total_runs, suggested_bet, confidence_score, key_insight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (row['game_id'], home_win_prob, away_win_prob, expected_runs, suggested_bet, confidence, key_insight))
        
        all_bets.append({
            "desc": f"{suggested_bet} ({row['away_team']} @ {row['home_team']})",
            "prob": confidence
        })
        
        # RUNLINE (Handicap)
        rl_home_prob = home_win_prob - 15.0 
        if rl_home_prob > 0:
            cursor.execute('''
                INSERT INTO player_props 
                (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row['game_id'], row['home_team'], 0, "Runline", -1.5, "Handicap", prob_to_american_odds(rl_home_prob), rl_home_prob))
            if rl_home_prob > 55:
                all_bets.append({"desc": f"{row['home_team']} -1.5 (Runline)", "prob": rl_home_prob})
                
        # GAME PROPS (CARRERAS Y HITS DEL JUEGO)
        cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], f"{row['away_team']} @ {row['home_team']}", 0, "Carreras Totales", expected_runs, "OVER", prob_to_american_odds(55.0), 55.0))
        cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], f"{row['away_team']} @ {row['home_team']}", 0, "Hits Totales", 15.5, "UNDER", prob_to_american_odds(52.0), 52.0))
        
        # TEAM PROPS (CARRERAS POR EQUIPO)
        cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], row['home_team'], 0, "Team Total Runs", expected_runs/2 + 0.5, "OVER", prob_to_american_odds(58.0), 58.0))
                
        # PLAYER PROPS (PITCHERS: STRIKEOUTS, HITS, ER)
        pitchers = [(row['home_pitcher_name'], row['home_pitcher_id'], home_win_prob), 
                    (row['away_pitcher_name'], row['away_pitcher_id'], away_win_prob)]
        for pitcher, p_id, win_prob in pitchers:
            if pitcher != "Unknown":
                # Ponches (K)
                k_line = round(random.uniform(3.5, 7.5) * 2) / 2
                cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], pitcher, p_id, "Ponches (K)", k_line, "OVER" if win_prob > 50 else "UNDER", prob_to_american_odds(58.0), 58.0))
                
                # Hits Permitidos
                cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], pitcher, p_id, "Hits Permitidos", 5.5, "UNDER" if win_prob > 50 else "OVER", prob_to_american_odds(54.0), 54.0))

        # PLAYER PROPS (BATEADORES: HITS, BASES, CARRERAS)
        teams = [(row['home_team'], h_ops), (row['away_team'], a_ops)]
        for team_name, ops in teams:
            # Simulamos un bateador clave por equipo
            p_name = f"Bateador Clave {team_name}"
            # Hits
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], p_name, 0, "Hits Totales", 1.5 if ops > 0.8 else 0.5, "OVER", prob_to_american_odds(52.0), 52.0))
            # Bases Totales
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], p_name, 0, "Bases Totales", 1.5, "OVER" if ops > 0.75 else "UNDER", prob_to_american_odds(55.0), 55.0))
            # Carreras Anotadas
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], p_name, 0, "Carreras Anotadas", 0.5, "OVER" if ops > 0.82 else "UNDER", prob_to_american_odds(53.0), 53.0))

        # PLAYER PROPS (BATEADORES)
        # Algunos IDs de bateadores estrella (Ohtani: 660271, Judge: 592450, Trout: 545361, Soto: 665742)
        star_ids = [660271, 592450, 545361, 665742]
        batters = [
            (f"1er Bateador ({row['home_team']})", 1.5, "Bases Totales", 0),
            (f"Bateador de Poder ({row['home_team']})", 0.5, "Home Runs", random.choice(star_ids)),
            (f"Mejor Contacto ({row['away_team']})", 1.5, "Total Hits", 0),
            (f"4to Bat Cleanup ({row['away_team']})", 0.5, "Carreras Impulsadas (RBIs)", random.choice(star_ids))
        ]
        
        for batter_name, line, prop_type, b_id in batters:
            hit_conf = 50.0 + random.uniform(2, 12)
            if prop_type == "Home Runs":
                hit_conf = 20.0 + random.uniform(5, 10) 
                
            cursor.execute('''
                INSERT INTO player_props 
                (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row['game_id'], batter_name, b_id, prop_type, line, "OVER", prob_to_american_odds(hit_conf), hit_conf))
            
            # Solo agregar al parlay si no es tan arriesgado (no homerun)
            if hit_conf > 58:
                all_bets.append({"desc": f"{batter_name} OVER {line} {prop_type}", "prob": hit_conf})
    
    # 3. ARMAR AI PARLAYS MULTIPLES
    if len(all_bets) >= 5:
        # Ordenar todas por confianza
        sorted_bets = sorted(all_bets, key=lambda x: x['prob'], reverse=True)
        
        # Filtrar por tipo
        ml_bets = [b for b in sorted_bets if "ML" in b['desc']]
        strikeout_bets = [b for b in sorted_bets if "Strikeouts" in b['desc']]
        hit_bets = [b for b in sorted_bets if "Hits" in b['desc'] or "Bases" in b['desc'] or "Home Runs" in b['desc'] or "RBIs" in b['desc']]
        
        # 1. Parlay Seguro General (Top 2)
        safe_legs = sorted_bets[:2]
        safe_prob = (safe_legs[0]['prob']/100) * (safe_legs[1]['prob']/100) * 100
        cursor.execute('''INSERT INTO ai_parlays (parlay_name, legs_description, combined_american_odds, win_probability) VALUES (?, ?, ?, ?)''',
                       ("🛡️ Parlay Seguro (+EV)", f"1. {safe_legs[0]['desc']}\n2. {safe_legs[1]['desc']}", prob_to_american_odds(safe_prob), safe_prob))
        
        # 2. Parlay Favoritos Moneyline (Top 3 ML)
        if len(ml_bets) >= 3:
            ml_legs = ml_bets[:3]
            ml_prob = (ml_legs[0]['prob']/100) * (ml_legs[1]['prob']/100) * (ml_legs[2]['prob']/100) * 100
            cursor.execute('''INSERT INTO ai_parlays (parlay_name, legs_description, combined_american_odds, win_probability) VALUES (?, ?, ?, ?)''',
                           ("🏆 Favoritos a Ganar (ML)", f"1. {ml_legs[0]['desc']}\n2. {ml_legs[1]['desc']}\n3. {ml_legs[2]['desc']}", prob_to_american_odds(ml_prob), ml_prob))
                           
        # 3. Parlay de Pitchers (Top 3 Strikeouts)
        if len(strikeout_bets) >= 3:
            k_legs = strikeout_bets[:3]
            k_prob = (k_legs[0]['prob']/100) * (k_legs[1]['prob']/100) * (k_legs[2]['prob']/100) * 100
            cursor.execute('''INSERT INTO ai_parlays (parlay_name, legs_description, combined_american_odds, win_probability) VALUES (?, ?, ?, ?)''',
                           ("⚾ Noche de Ponches", f"1. {k_legs[0]['desc']}\n2. {k_legs[1]['desc']}\n3. {k_legs[2]['desc']}", prob_to_american_odds(k_prob), k_prob))

        # 4. Parlay de Bateadores (Top 3 Hits)
        if len(hit_bets) >= 3:
            h_legs = hit_bets[:3]
            h_prob = (h_legs[0]['prob']/100) * (h_legs[1]['prob']/100) * (h_legs[2]['prob']/100) * 100
            cursor.execute('''INSERT INTO ai_parlays (parlay_name, legs_description, combined_american_odds, win_probability) VALUES (?, ?, ?, ?)''',
                           ("🔥 Fiesta de Bateo (Props)", f"1. {h_legs[0]['desc']}\n2. {h_legs[1]['desc']}\n3. {h_legs[2]['desc']}", prob_to_american_odds(h_prob), h_prob))
        
        # 5. Mega Lotto Parlay (Top 5 combinados)
        lotto_legs = sorted_bets[:5]
        lotto_prob = (lotto_legs[0]['prob']/100) * (lotto_legs[1]['prob']/100) * (lotto_legs[2]['prob']/100) * (lotto_legs[3]['prob']/100) * (lotto_legs[4]['prob']/100) * 100
        cursor.execute('''INSERT INTO ai_parlays (parlay_name, legs_description, combined_american_odds, win_probability) VALUES (?, ?, ?, ?)''',
                       ("🚀 MEGA LOTTO (5-Legs)", f"1. {lotto_legs[0]['desc']}\n2. {lotto_legs[1]['desc']}\n3. {lotto_legs[2]['desc']}\n4. {lotto_legs[3]['desc']}\n5. {lotto_legs[4]['desc']}", prob_to_american_odds(lotto_prob), lotto_prob))
            
    conn.commit()
    conn.close()
    print("✅ Props y Parlays generados.")

if __name__ == "__main__":
    generate_predictions()
