import sqlite3
import pandas as pd
import random
from database import get_connection

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
        # 1. PREDECIR MONEYLINE / TOTALS
        home_win_prob = 55.0 + random.uniform(-10, 15)
        away_win_prob = 100.0 - home_win_prob
        expected_runs = 8.5
        
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
            
        cursor.execute('''
            INSERT INTO predictions 
            (game_id, home_win_prob, away_win_prob, expected_total_runs, suggested_bet, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (row['game_id'], home_win_prob, away_win_prob, expected_runs, suggested_bet, confidence))
        
        all_bets.append({
            "desc": f"{suggested_bet} ({row['away_team']} @ {row['home_team']})",
            "prob": confidence
        })
        
        # RUNLINE (Handicap)
        rl_home_prob = home_win_prob - 15.0 
        if rl_home_prob > 0:
            cursor.execute('''
                INSERT INTO player_props 
                (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (row['game_id'], row['home_team'], "Runline", -1.5, "Handicap", prob_to_american_odds(rl_home_prob), rl_home_prob))
            if rl_home_prob > 55:
                all_bets.append({"desc": f"{row['home_team']} -1.5 (Runline)", "prob": rl_home_prob})
                
        # GAME PROPS (CARRERAS Y HITS DEL JUEGO)
        cursor.execute('''INSERT INTO player_props (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], f"{row['away_team']} @ {row['home_team']}", "Carreras Totales", expected_runs, "OVER", prob_to_american_odds(55.0), 55.0))
        cursor.execute('''INSERT INTO player_props (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], f"{row['away_team']} @ {row['home_team']}", "Hits Totales", 15.5, "UNDER", prob_to_american_odds(52.0), 52.0))
        
        # TEAM PROPS (CARRERAS POR EQUIPO)
        cursor.execute('''INSERT INTO player_props (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                       (row['game_id'], row['home_team'], "Team Total Runs", expected_runs/2 + 0.5, "OVER", prob_to_american_odds(58.0), 58.0))
                
        # PLAYER PROPS (PITCHERS: STRIKEOUTS, HITS PERMITIDOS, CARRERAS LIMPIAS)
        pitchers = [(row['home_pitcher_name'], home_win_prob), (row['away_pitcher_name'], away_win_prob)]
        for pitcher, win_prob in pitchers:
            if pitcher != "Unknown":
                # Strikeouts
                k_line = round(random.uniform(4.5, 8.5) * 2) / 2
                is_over = win_prob > 50
                side_k = "OVER" if is_over else "UNDER"
                prop_conf = 55.0 + random.uniform(0, 15)
                cursor.execute('''
                    INSERT INTO player_props 
                    (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['game_id'], pitcher, "Strikeouts", k_line, side_k, prob_to_american_odds(prop_conf), prop_conf))
                if prop_conf > 60:
                    all_bets.append({"desc": f"{pitcher} {side_k} {k_line} Strikeouts", "prob": prop_conf})
                
                # Hits Permitidos
                hits_line = round(random.uniform(4.5, 6.5) * 2) / 2
                cursor.execute('''
                    INSERT INTO player_props 
                    (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['game_id'], pitcher, "Hits Permitidos", hits_line, "UNDER" if is_over else "OVER", prob_to_american_odds(53.0), 53.0))
                
                # Carreras Limpias (Earned Runs)
                er_line = 2.5
                cursor.execute('''
                    INSERT INTO player_props 
                    (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['game_id'], pitcher, "Carreras Limpias", er_line, "UNDER" if is_over else "OVER", prob_to_american_odds(54.0), 54.0))

        # PLAYER PROPS (BATEADORES: HITS, HOMERUNS, BASES TOTALES)
        batters = [
            (f"1er Bateador ({row['home_team']})", 1.5, "Bases Totales"),
            (f"Bateador de Poder ({row['home_team']})", 0.5, "Home Runs"),
            (f"Mejor Contacto ({row['away_team']})", 1.5, "Total Hits"),
            (f"4to Bat Cleanup ({row['away_team']})", 0.5, "Carreras Impulsadas (RBIs)")
        ]
        
        for batter_name, line, prop_type in batters:
            hit_conf = 50.0 + random.uniform(2, 12)
            # Para Home Runs las cuotas son positivas y probabilidades mas bajas
            if prop_type == "Home Runs":
                hit_conf = 20.0 + random.uniform(5, 10) 
                
            cursor.execute('''
                INSERT INTO player_props 
                (game_id, player_name, prop_type, line, suggested_side, american_odds, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (row['game_id'], batter_name, prop_type, line, "OVER", prob_to_american_odds(hit_conf), hit_conf))
            
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
