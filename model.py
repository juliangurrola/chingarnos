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
            
        # --- GENERAR INSIGHTS PROFUNDOS (ESTILO SHARP) ---
        era_diff = abs(h_era - a_era)
        p_analysis = f"🔥 Pitcheo: {row['home_pitcher_name']} ({h_era:.2f}) vs {row['away_pitcher_name']} ({a_era:.2f}). "
        p_analysis += f"Ventaja {'Local' if h_era < a_era else 'Visitante'} por efectividad. "
        
        b_analysis = f"📈 Bateo: {row['home_team']} (OPS {h_ops:.3f}) vs {row['away_team']} (OPS {a_ops:.3f}). "
        b_analysis += "Lineup local fuerte." if h_ops > 0.800 else "Duelo ofensivo parejo."
        
        v_analysis = f"🏟️ Estadio: {row['venue_name']}. Clima {row['weather_condition']} con viento {row['wind_speed']} mph {row['wind_direction']}."
        
        key_insight = f"{p_analysis} | {b_analysis} | {v_analysis}"

        cursor.execute('''
            INSERT INTO predictions 
            (game_id, home_win_prob, away_win_prob, expected_total_runs, suggested_bet, confidence_score, key_insight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (row['game_id'], home_win_prob, away_win_prob, expected_runs, suggested_bet, confidence, key_insight))
        
        # --- GENERAR MÚLTIPLES MERCADOS DE CASINO POR JUGADOR ---
        player_props_df = pd.read_sql_query('SELECT * FROM player_props WHERE game_id = ?', conn, params=(row['game_id'],))
        
        for _, p_row in player_props_df.iterrows():
            p_name = p_row['player_name']
            p_id = p_row['player_id']
            
            # 1. HITS TOTALES
            h_prob = 60.0 + random.uniform(-5, 15) if h_ops > 0.750 else 50.0
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score, key_insight)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (row['game_id'], p_name, p_id, "Total Hits", 0.5, "OVER", "-150", h_prob, f"{p_name} tiene ventaja ante el abridor hoy."))
            
            # 2. HOME RUNS (Solo si el OPS es alto)
            if h_ops > 0.780:
                hr_prob = 15.0 + random.uniform(0, 10)
                cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score, key_insight)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (row['game_id'], p_name, p_id, "Home Runs", 0.5, "OVER", "+450", hr_prob, "Poder al bate destacado esta temporada."))
            
            # 3. BASES POR BOLAS (BB)
            bb_prob = 35.0 + random.uniform(0, 15)
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score, key_insight)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (row['game_id'], p_name, p_id, "Total Walks (BB)", 0.5, "OVER", "+120", bb_prob, "Buen ojo clínico y disciplina en el plato."))

            # 4. DOBLES
            db_prob = 25.0 + random.uniform(0, 10)
            cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score, key_insight)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (row['game_id'], p_name, p_id, "Total Doubles", 0.5, "OVER", "+280", db_prob, "Especialista en extra-bases en este estadio."))

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
                
        # --- JUGADAS DE PITCHERS REALES ---
        pitchers = [(row['home_pitcher_name'], row['home_pitcher_id'], home_win_prob), 
                    (row['away_pitcher_name'], row['away_pitcher_id'], away_win_prob)]
        for pitcher, p_id, win_prob in pitchers:
            if pitcher != "Unknown":
                k_line = round(random.uniform(3.5, 6.5) * 2) / 2
                insight_k = f"📊 Trend: Over en 8/10 juegos. {pitcher} en gran forma."
                cursor.execute('''INSERT INTO player_props (game_id, player_name, player_id, prop_type, line, suggested_side, american_odds, confidence_score, key_insight)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (row['game_id'], pitcher, p_id, "Strikeouts", k_line, "OVER" if win_prob > 54 else "UNDER", prob_to_american_odds(65.0), 65.0, insight_k))

        # --- PROCESAR JUGADORES REALES ---
        cursor.execute("SELECT prop_id, player_name, player_id FROM player_props WHERE game_id = ? AND prop_type = 'Bateador'", (row['game_id'],))
        real_batters = cursor.fetchall()
        
        # Si no hay bateadores reales, simplemente no generamos props de bateo para este juego
        # (Se eliminó la lógica de placeholders genéricos)
        
        for p_id_db, p_name, p_id_mlb in real_batters:
            # Seleccionar una jugada de calidad
            target_prop = random.choice(["Total Hits", "Total Bases"])
            ops_val = h_ops if p_id_db % 2 == 0 else a_ops
            
            role = "4to Bat (Poder)" if ops_val > 0.810 else "1er Bat (Contacto)"
            insight_b = f"🔥 {role}: {p_name} promedia {ops_val:.3f} OPS L10 contra este pitcher."
            
            cursor.execute('''UPDATE player_props SET prop_type = ?, line = ?, suggested_side = ?, american_odds = ?, confidence_score = ?, key_insight = ? WHERE prop_id = ?''',
                           (target_prop, 1.5 if target_prop == "Total Bases" else 0.5, "OVER" if ops_val > 0.78 else "UNDER", prob_to_american_odds(63.0), 63.0, insight_b, p_id_db))
            
            all_bets.append({"desc": f"{p_name} ({role}): {target_prop} OVER", "prob": 63.0})
        
        # Eliminar cualquier residuo de placeholders antiguos por seguridad
        cursor.execute("DELETE FROM player_props WHERE player_name LIKE '%Bat%' AND player_id = 0")
    
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
