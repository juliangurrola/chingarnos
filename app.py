import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from database import get_connection, init_db

# Inicializar DB si no existe (importante para la nube)
init_db()

st.set_page_config(page_title="A chingarnos al casino x Elven", page_icon="🤑", layout="wide")

# UI/UX PRO MAX DESIGN SYSTEM (INVISIBLE)
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="st-"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; letter-spacing: 1px; }
    .stApp { background: radial-gradient(circle at top right, #1e1e2f, #0d0d0d); }
    [data-testid="stExpander"], [data-testid="stMetric"], .st-emotion-cache-16ids9n {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
    }
    .stButton>button {
        background: linear-gradient(90deg, #FF5722, #FF9800) !important;
        border: none !important; color: white !important; font-weight: bold !important;
        border-radius: 8px !important; text-transform: uppercase;
    }
    @media (max-width: 768px) {
        .floating-footer {
            position: fixed; bottom: 20px; left: 5%; width: 90%;
            background: rgba(30, 30, 30, 0.95) !important;
            backdrop-filter: blur(15px) !important;
            padding: 12px 20px; border: 1px solid #FF5722;
            border-radius: 50px; z-index: 1000;
            display: flex; justify-content: space-between; align-items: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
    }
    </style>
""", unsafe_allow_html=True)

# Helper para calcular cuota combinada
def calc_parlay_odds(probs):
    if not probs: return "N/A"
    combined_prob = 1.0
    for p in probs:
        combined_prob *= (p / 100.0)
    
    if combined_prob <= 0 or combined_prob >= 1:
        return "N/A"
    
    if combined_prob > 0.5:
        odds = - (combined_prob / (1 - combined_prob)) * 100
    else:
        odds = ((1 - combined_prob) / combined_prob) * 100
        
    return int(odds)

# UI PRINCIPAL
st.markdown("<br>", unsafe_allow_html=True)
col_logo, col_title = st.columns([1, 3])
with col_logo:
    try:
        st.image("elven_logo.jpg", width=150)
    except: pass
with col_title:
    st.title("🤑 A CHINGARNOS AL CASINO")
    st.subheader("BY ELVEN MX | PRO MAX EDITION")

st.sidebar.header("⚙️ Opciones")
if st.sidebar.button("🔄 Actualizar Datos"):
    import subprocess
    import sys
    with st.spinner("Descargando datos..."):
        subprocess.run([sys.executable, "scraper.py"])
        subprocess.run([sys.executable, "model.py"])
    st.sidebar.success("¡Datos actualizados!")
    st.rerun()

conn = get_connection()
try:
    games_df = pd.read_sql_query('''
        SELECT d.game_id, d.home_team, d.away_team, d.venue_name, d.weather_condition, d.wind_speed, d.wind_direction,
               d.home_pitcher_name, d.away_pitcher_name, p.home_win_prob, p.away_win_prob, 
               p.expected_total_runs, p.suggested_bet, p.confidence_score, p.key_insight
        FROM daily_schedule d
        JOIN predictions p ON d.game_id = p.game_id
    ''', conn)
    props_df = pd.read_sql_query('SELECT * FROM player_props', conn)
    parlays_df = pd.read_sql_query('SELECT * FROM ai_parlays', conn)
except:
    games_df = pd.DataFrame()
    props_df = pd.DataFrame()
    parlays_df = pd.DataFrame()

conn.close()

if games_df.empty:
    st.warning("⚠️ La base de datos está vacía en este servidor.")
    st.info("Por favor, haz clic en el botón **'🔄 Actualizar Datos'** en el menú de la izquierda para descargar las estadísticas de hoy y generar las predicciones.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Player Props", "🤑 Parlays Sugeridos", "📝 Armador de Parlays", "📊 Juegos Principales"])

# TAB 1: PLAYER PROPS
with tab1:
    st.subheader("🔥 Mejores Apuestas por Jugador")
    cols = st.columns(3)
    # Mostramos los mejores 15 props para no saturar
    best_props = props_df.sort_values(by='confidence_score', ascending=False).head(15)
    
    if 'selected_bets' not in st.session_state:
        st.session_state['selected_bets'] = []

    for i, (_, row) in enumerate(best_props.iterrows()):
        with cols[i % 3]:
            with st.container(border=True):
                # FOTO DEL JUGADOR
                p_id = row.get('player_id', 0)
                if pd.notnull(p_id) and p_id > 0:
                    img_url = f"https://img.mlbstatic.com/mlb-photos/person/{int(p_id)}@3x.jpg"
                    st.markdown(f"<div style='text-align:center;'><img src='{img_url}' style='border-radius:50%; width:100px; border:3px solid #FF5722;'></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align:center; font-size:60px;'>⚾</div>", unsafe_allow_html=True)
                
                st.markdown(f"<h4 style='text-align:center; margin-bottom:0;'>{row['player_name']}</h4>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center;'>**{row['suggested_side']} {row['line']} {row['prop_type']}**</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center;'>Momio: **{row['american_odds']}**</div>", unsafe_allow_html=True)
                
                # Checkbox para seleccionar
                desc_p = f"{row['player_name']}: {row['suggested_side']} {row['line']} {row['prop_type']}"
                prob_p = row['confidence_score']
                
                # Sincronizar estado
                is_selected = any(b['desc'] == desc_p for b in st.session_state['selected_bets'])
                
                if st.checkbox("Seleccionar para Parlay", value=is_selected, key=f"best_p_{row['prop_id']}"):
                    if not any(b['desc'] == desc_p for b in st.session_state['selected_bets']):
                        st.session_state['selected_bets'].append({"desc": desc_p, "prob": prob_p})
                else:
                    if any(b['desc'] == desc_p for b in st.session_state['selected_bets']):
                        st.session_state['selected_bets'] = [b for b in st.session_state['selected_bets'] if b['desc'] != desc_p]
                
                st.markdown(f"<h2 style='color:#FF5722; text-align:center; margin-top:0;'>{row['confidence_score']:.1f}%</h2>", unsafe_allow_html=True)

# TAB 2: PARLAYS DE LA IA
with tab2:
    st.subheader("🤖 Parlays Sugeridos por Inteligencia Artificial")
    for _, row in parlays_df.iterrows():
        st.success(f"### {row['parlay_name']}\n\n"
                   f"**Selecciones:**\n{row['legs_description']}\n\n"
                   f"**Momio Americano Combinado:** {row['combined_american_odds']}\n\n"
                   f"**Probabilidad Matemática:** {row['win_probability']:.1f}%")

# TAB 3: ARMADOR DE PARLAYS
with tab3:
    st.subheader("📝 Construye tu propio Parlay")
    st.markdown("Abre los partidos para seleccionar tus jugadas. El Momio Combinado se calcula a la izquierda.")
    
    if 'selected_bets' not in st.session_state:
        st.session_state['selected_bets'] = []
        
    from datetime import datetime
    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y-%m-%d')
    
    # SECCION HOY
    st.markdown("### 🔥 JUEGOS DE HOY")
    # Filtro flexible por si hay espacios
    games_df['game_date'] = games_df['game_date'].str.strip()
    today_games = games_df[games_df['game_date'] == today_str]
    if today_games.empty:
        st.write("No hay juegos programados para hoy.")
    else:
        for i, row in today_games.iterrows():
            with st.expander(f"🏟️ {row['away_team']} @ {row['home_team']}", expanded=False):
                # ... (resto del codigo de seleccion se mantiene igual)
                st.markdown("#### 🏆 Ganador del Partido")
                col1, col2 = st.columns(2)
                desc_h = f"{row['home_team']} ML"
                prob_h = row['home_win_prob']
                with col1:
                    with st.container(border=True):
                        if st.checkbox(f"**{desc_h}**", key=f"h_{row['game_id']}"):
                            if {"desc": desc_h, "prob": prob_h} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_h, "prob": prob_h})
                        else:
                            if {"desc": desc_h, "prob": prob_h} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_h, "prob": prob_h})
                        st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_h:.1f}%</h3>", unsafe_allow_html=True)
                desc_a = f"{row['away_team']} ML"
                prob_a = row['away_win_prob']
                with col2:
                    with st.container(border=True):
                        if st.checkbox(f"**{desc_a}**", key=f"a_{row['game_id']}"):
                            if {"desc": desc_a, "prob": prob_a} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_a, "prob": prob_a})
                        else:
                            if {"desc": desc_a, "prob": prob_a} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_a, "prob": prob_a})
                        st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_a:.1f}%</h3>", unsafe_allow_html=True)
                
                # Props
                game_props = props_df[props_df['game_id'] == row['game_id']]
                p_cols = st.columns(2)
                for idx, prop in game_props.iterrows():
                    with p_cols[idx % 2]:
                        with st.container(border=True):
                            desc_p = f"{prop['player_name']}: {prop['suggested_side']} {prop['line']} {prop['prop_type']}"
                            prob_p = prop['confidence_score']
                            if st.checkbox(f"**{desc_p}**", key=f"p_{prop['prop_id']}"):
                                if {"desc": desc_p, "prob": prob_p} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_p, "prob": prob_p})
                            else:
                                if {"desc": desc_p, "prob": prob_p} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_p, "prob": prob_p})
                            st.markdown(f"<h3 style='color:#2196F3; margin-top:-10px;'>{prob_p:.1f}%</h3>", unsafe_allow_html=True)

    # SECCION MAÑANA
    st.markdown("---")
    st.markdown("### 📅 PRÓXIMOS JUEGOS (MAÑANA)")
    tomorrow_games = games_df[games_df['game_date'] != today_str]
    if tomorrow_games.empty:
        st.write("No hay juegos programados para mañana.")
    else:
        for i, row in tomorrow_games.iterrows():
            with st.expander(f"🏟️ {row['away_team']} @ {row['home_team']} ({row['game_date']})", expanded=False):
                # (Repetimos la logica para mañana)
                st.markdown("#### 🏆 Ganador del Partido")
                col1, col2 = st.columns(2)
                desc_h = f"{row['home_team']} ML"; prob_h = row['home_win_prob']
                with col1:
                    with st.container(border=True):
                        if st.checkbox(f"**{desc_h}**", key=f"tm_h_{row['game_id']}"):
                            if {"desc": desc_h, "prob": prob_h} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_h, "prob": prob_h})
                        else:
                            if {"desc": desc_h, "prob": prob_h} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_h, "prob": prob_h})
                        st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_h:.1f}%</h3>", unsafe_allow_html=True)
                desc_a = f"{row['away_team']} ML"; prob_a = row['away_win_prob']
                with col2:
                    with st.container(border=True):
                        if st.checkbox(f"**{desc_a}**", key=f"tm_a_{row['game_id']}"):
                            if {"desc": desc_a, "prob": prob_a} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_a, "prob": prob_a})
                        else:
                            if {"desc": desc_a, "prob": prob_a} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_a, "prob": prob_a})
                        st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_a:.1f}%</h3>", unsafe_allow_html=True)
                
                game_props = props_df[props_df['game_id'] == row['game_id']]
                p_cols = st.columns(2)
                for idx, prop in game_props.iterrows():
                    with p_cols[idx % 2]:
                        with st.container(border=True):
                            desc_p = f"{prop['player_name']}: {prop['suggested_side']} {prop['line']} {prop['prop_type']}"
                            prob_p = prop['confidence_score']
                            if st.checkbox(f"**{desc_p}**", key=f"tm_p_{prop['prop_id']}"):
                                if {"desc": desc_p, "prob": prob_p} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_p, "prob": prob_p})
                            else:
                                if {"desc": desc_p, "prob": prob_p} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_p, "prob": prob_p})
                            st.markdown(f"<h3 style='color:#2196F3; margin-top:-10px;'>{prob_p:.1f}%</h3>", unsafe_allow_html=True)

    # --- RECIBO DE APUESTA (AHORA EN EL AREA PRINCIPAL PARA MOVILES) ---
    st.markdown("---")
    with st.container(border=True):
        st.subheader("🛒 Tu Recibo de Apuesta")
        
        if len(st.session_state['selected_bets']) == 0:
            st.info("Selecciona alguna apuesta arriba para armar tu ticket.")
        else:
            col_rec1, col_rec2 = st.columns([2, 1])
            
            with col_rec1:
                st.markdown("**Selecciones:**")
                probs = []
                for b in st.session_state['selected_bets']:
                    st.write(f"✅ {b['desc']}")
                    probs.append(b['prob'])
                
                wager = st.number_input("Monto a apostar ($):", min_value=10.0, value=100.0, step=10.0, key="wager_main")
            
            with col_rec2:
                combined_odds = calc_parlay_odds(probs)
                if combined_odds != "N/A":
                    display_odds = f"+{combined_odds}" if combined_odds > 0 else f"{combined_odds}"
                    st.metric("MOMIO PARLAY", display_odds)
                    
                    # Calcular ganancia
                    if combined_odds > 0:
                        profit = wager * (combined_odds / 100.0)
                    else:
                        profit = wager * (100.0 / abs(combined_odds))
                    
                    payout = wager + profit
                    st.metric("PAGO TOTAL", f"${payout:.2f}", delta=f"${profit:.2f} NETO")
                else:
                    st.error("Error en Momio")

            # BOTON WHATSAPP GRANDE (FULL WIDTH)
            if combined_odds != "N/A":
                msg = f"🎰 *MI PARLAY GANADOR* (A chingarnos al casino x Elven)\n\n"
                for b in st.session_state['selected_bets']:
                    msg += f"• {b['desc']}\n"
                msg += f"\n*MOMIO:* {display_odds}\n"
                msg += f"*APUESTA:* ${wager:.2f}\n"
                msg += f"*PAGO ESTIMADO:* ${payout:.2f}\n\n"
                msg += "¡A cobrar! ⚾💸"
                
                encoded_msg = urllib.parse.quote(msg)
                wa_url = f"https://wa.me/?text={encoded_msg}"
                
            # BARRA FLOTANTE PARA MOVILES (STICKY FOOTER)
            st.markdown(f'''
                <div class="floating-footer">
                    <div style="color:white;">
                        <div style="font-size:12px; opacity:0.8;">MOMIO TOTAL</div>
                        <div style="font-size:18px; font-weight:bold; color:#FF5722;">{display_odds}</div>
                    </div>
                    <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                        <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; cursor:pointer;">
                            📲 ENVIAR POR WA
                        </button>
                    </a>
                </div>
            ''', unsafe_allow_html=True)

            # Recibo normal (se mantiene para escritorio)
            st.markdown(f'''
                <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                    <div style="width:100%; background-color:#25D366; color:white; text-align:center; padding:15px; border-radius:10px; cursor:pointer; font-weight:bold; font-size:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        📲 ENVIAR TICKET POR WHATSAPP
                    </div>
                </a>
            ''', unsafe_allow_html=True)


# TAB 4: JUEGOS PRINCIPALES
with tab4:
    st.subheader("📊 Análisis de Todos los Partidos")
    
    if not games_df.empty:
        from datetime import datetime
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # Ordenar por fecha
        games_df['game_date_dt'] = pd.to_datetime(games_df['game_date'])
        sorted_games = games_df.sort_values(by=['game_date_dt', 'home_team'])
        
        for _, row in sorted_games.iterrows():
            date_label = "HOY ⚾" if row['game_date'] == today_str else f"MAÑANA ({row['game_date']}) 📅"
            
            with st.expander(f"{date_label} | {row['away_team']} @ {row['home_team']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Pitchers Abridores:**")
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        if row['home_pitcher_id'] > 0:
                            st.image(f"https://img.mlbstatic.com/mlb-photos/person/{row['home_pitcher_id']}@3x.jpg", width=80)
                        st.write(f"🏠 {row['home_team']}: {row['home_pitcher_name']}")
                    with col_p2:
                        if row['away_pitcher_id'] > 0:
                            st.image(f"https://img.mlbstatic.com/mlb-photos/person/{row['away_pitcher_id']}@3x.jpg", width=80)
                        st.write(f"✈️ {row['away_team']}: {row['away_pitcher_name']}")
                with col2:
                    st.markdown("**Condiciones (Estadio/Clima):**")
                    st.write(f"🌤️ {row['weather_condition']}")
                    st.write(f"💨 Viento: {row['wind_speed']} mph, {row['wind_direction']}")
                
                st.progress(int(row['home_win_prob']), text=f"Probabilidad de Local ({row['home_team']}): {row['home_win_prob']:.1f}%")
                st.metric("Carreras Totales Esperadas", f"{row['expected_total_runs']} carreras")
                
                with st.container(border=True):
                    st.markdown("#### 📌 Análisis de Referencia (Insights)")
                    st.info(row['key_insight'])
