import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from database import get_connection, init_db

# Inicializar DB si no existe (importante para la nube)
init_db()

# INICIALIZACION GLOBAL DE SESION
if 'selected_bets' not in st.session_state:
    st.session_state['selected_bets'] = []

st.set_page_config(page_title="MLB Predictor x Elven MX", page_icon="🤑", layout="wide")

# DISEÑO MINIMALISTA
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    [data-testid="stExpander"], [data-testid="stMetric"] { background-color: #1A1C24 !important; border: 1px solid #333 !important; }
    .stButton>button { background-color: #FF5722 !important; border: none !important; color: white !important; }
    
    /* Menu de Pestañas Fijo (Sticky) */
    [data-testid="stTabs"] {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: #0E1117;
        padding-top: 10px;
        padding-bottom: 5px;
    }
    
    @media (max-width: 768px) {
        .floating-footer {
            position: fixed; bottom: 0; left: 0; width: 100%;
            background-color: #1A1C24; padding: 15px; border-top: 2px solid #FF5722;
            z-index: 1000; display: flex; justify-content: space-between; align-items: center;
        }
        .main { padding-bottom: 120px !important; }
    }
    </style>
""", unsafe_allow_html=True)

# Helper para añadir/quitar apuestas (CALLBACK)
def toggle_bet(desc, prob):
    current_bets = st.session_state.get('selected_bets', [])
    exists = any(b['desc'] == desc for b in current_bets)
    if exists:
        st.session_state['selected_bets'] = [b for b in current_bets if b['desc'] != desc]
    else:
        st.session_state['selected_bets'].append({"desc": desc, "prob": prob})

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
    st.title("🤑 MLB Predictor x Elven MX")
    st.markdown("Análisis inteligente de apuestas.")

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
        SELECT d.game_id, d.game_date, d.home_team, d.away_team, d.venue_name, d.weather_condition, d.wind_speed, d.wind_direction,
               d.home_pitcher_name, d.away_pitcher_name, d.home_pitcher_id, d.away_pitcher_id,
               p.home_win_prob, p.away_win_prob, 
               p.expected_total_runs, p.suggested_bet, p.confidence_score, p.key_insight
        FROM daily_schedule d
        JOIN predictions p ON d.game_id = p.game_id
    ''', conn)
    props_df = pd.read_sql_query('''
        SELECT p.*, d.game_date 
        FROM player_props p
        JOIN daily_schedule d ON p.game_id = d.game_id
    ''', conn)
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
    st.subheader("🔥 TOP 10 RECOMENDACIONES DEL DÍA")
    best_props = props_df.sort_values(by='confidence_score', ascending=False).head(10)
    
    cols = st.columns(2) 
    for i, (_, row) in enumerate(best_props.iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                # FECHA DE LA APUESTA
                from datetime import datetime
                today_s = datetime.now().strftime('%Y-%m-%d')
                badge_color = "#FF5722" if row['game_date'] == today_s else "#2196F3"
                badge_text = "HOY" if row['game_date'] == today_s else "MAÑANA"
                st.markdown(f"<div style='text-align:right;'><span style='background:{badge_color}; color:white; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;'>{badge_text}</span></div>", unsafe_allow_html=True)
                
                # FOTO DEL JUGADOR
                p_id = row.get('player_id', 0)
                try:
                    p_id_int = int(float(p_id))
                except: p_id_int = 0

                if p_id_int > 0:
                    img_url = f"https://img.mlbstatic.com/mlb-photos/person/{p_id_int}@3x.jpg"
                    st.markdown(f"<div style='text-align:center; margin-top:5px;'><img src='https://img.mlbstatic.com/mlb-photos/person/{p_id_int}@3x.jpg' style='border-radius:10px; width:100%; border:1px solid #30363D;'></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align:center; font-size:40px; margin-top:5px;'>⚾</div>", unsafe_allow_html=True)
                
                st.markdown(f"<h4 style='text-align:center; margin-bottom:0; font-size:16px;'>{row['player_name']}</h4>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center; font-size:14px;'>**{row['suggested_side']} {row['line']}**</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center; font-size:12px; opacity:0.8;'>{row['prop_type']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center; color:#FF5722; font-weight:bold;'>{row['american_odds']}</div>", unsafe_allow_html=True)
                
                # BOTON DE ACCION (Añadir/Quitar con CALLBACK)
                desc_p = f"{row['player_name']}: {row['suggested_side']} {row['line']} {row['prop_type']}"
                is_selected = any(b['desc'] == desc_p for b in st.session_state['selected_bets'])
                
                btn_label = "✅ EN TICKET" if is_selected else "➕ AÑADIR"
                st.button(btn_label, key=f"bp_{row['prop_id']}", use_container_width=True, on_click=toggle_bet, args=(desc_p, row['confidence_score']))
                
                st.markdown(f"<div style='text-align:center; font-size:22px; font-weight:bold; color:#4CAF50;'>{row['confidence_score']:.1f}%</div>", unsafe_allow_html=True)
                if row.get('key_insight'):
                    st.caption(f"💡 {row['key_insight']}")

# TAB 2: PARLAYS DE LA IA
with tab2:
    st.subheader("🤖 Parlays Sugeridos por Inteligencia Artificial")
    for _, row in parlays_df.iterrows():
        with st.container(border=True):
            st.success(f"### {row['parlay_name']}\n\n"
                       f"**Selecciones:**\n{row['legs_description']}\n\n"
                       f"**Momio:** {row['combined_american_odds']} | **Prob:** {row['win_probability']:.1f}%")
            
            # Boton para añadir al ticket
            p_desc = f"IA PARLAY: {row['parlay_name']}"
            p_prob = row['win_probability']
            
            if st.button(f"➕ Añadir {row['parlay_name']} al Ticket", key=f"ai_p_{row['parlay_id']}"):
                if not any(b['desc'] == p_desc for b in st.session_state['selected_bets']):
                    st.session_state['selected_bets'].append({"desc": p_desc, "prob": p_prob})
                    st.toast(f"✅ {row['parlay_name']} añadido!")
                else:
                    st.warning("Este parlay ya está en tu ticket.")

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

        else:
            st.info("👋 ¡Hola! Selecciona jugadas en los partidos de arriba para armar tu parlay.")
            
        # --- RESUMEN DEL TICKET DENTRO DE LA PESTAÑA ---
        if 'selected_bets' in st.session_state and len(st.session_state['selected_bets']) > 0:
            with st.container(border=True):
                st.write("### 📄 Resumen de este Parlay")
                probs_tab = [b['prob'] for b in st.session_state['selected_bets']]
                c_odds = calc_parlay_odds(probs_tab)
                d_odds = f"+{c_odds}" if c_odds != "N/A" and c_odds > 0 else f"{c_odds}"
                st.write(f"**Momio Total:** {d_odds}")
                st.write(f"**Selecciones:** {len(st.session_state['selected_bets'])}")
                st.info("👉 El ticket completo con calculadora y botón de WhatsApp está al final de la página.")

# --- SECCION LATERAL (SIDEBAR): RECIBO DE APUESTA ---
with st.sidebar:
    st.markdown("---")
    st.subheader("🛒 Tu Ticket")
    
    # Inicializar variables para evitar errores
    combined_odds = "N/A"
    display_odds = "0"
    payout = 0.0
    profit = 0.0
    wa_url = "#"
    
    if 'selected_bets' in st.session_state and len(st.session_state['selected_bets']) > 0:
        st.markdown("**Selecciones:**")
        probs = []
        for b in st.session_state['selected_bets']:
            with st.container(border=True):
                st.caption(f"✅ {b['desc']}")
                probs.append(b['prob'])
        
        wager = st.number_input("Monto a apostar ($):", min_value=10.0, value=100.0, step=10.0, key="wager_side")
        
        combined_odds = calc_parlay_odds(probs)
        if combined_odds != "N/A":
            display_odds = f"+{combined_odds}" if combined_odds > 0 else f"{combined_odds}"
            st.metric("MOMIO", display_odds)
            if combined_odds > 0: profit = wager * (combined_odds / 100.0)
            else: profit = wager * (100.0 / abs(combined_odds))
            payout = wager + profit
            st.metric("PAGO TOTAL", f"${payout:.2f}")
        
        # Generar link de WhatsApp
        msg = f"🎰 *MI PARLAY GANADOR* (Elven MX)\n\n"
        for b in st.session_state['selected_bets']:
            msg += f"• {b['desc']}\n"
        msg += f"\n*MOMIO:* {display_odds}\n*APUESTA:* ${wager:.2f}\n*PAGO:* ${payout:.2f}\n\n¡A cobrar! ⚾💸"
        wa_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
        
        # Boton grande para WhatsApp (Llamativo)
        st.markdown(f'''
            <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                <div style="width:100%; background: linear-gradient(90deg, #25D366, #128C7E); color:white; text-align:center; padding:18px; border-radius:15px; cursor:pointer; font-weight:bold; font-size:22px; box-shadow: 0 6px 20px rgba(37,211,102,0.4); margin-top:10px;">
                    📲 ENVIAR TICKET
                </div>
            </a>
        ''', unsafe_allow_html=True)
        
        if st.button("🗑️ Limpiar Ticket"):
            st.session_state['selected_bets'] = []
            st.rerun()
    else:
        st.info("Selecciona jugadas para armar tu parlay.")

        # BARRA FLOTANTE PARA MOVILES (STICKY FOOTER - Se mantiene para moviles donde no hay sidebar visible)
        st.markdown(f'''
            <div class="floating-footer">
                <div style="color:white; flex-grow:1;">
                    <div style="font-size:10px; font-weight:bold; color:#4CAF50;">{len(st.session_state['selected_bets'])} JUGADAS</div>
                    <div style="font-size:18px; font-weight:bold; color:#FF5722;">{display_odds}</div>
                </div>
                <div style="color:white; text-align:center; padding-right:15px;">
                    <div style="font-size:10px; opacity:0.8;">PAGO</div>
                    <div style="font-size:16px; font-weight:bold; color:#FFF;">${payout:.0f}</div>
                </div>
                <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                    <button style="background-color:#25D366; color:white; border:none; padding:12px 20px; border-radius:30px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0 4px 15px rgba(37,211,102,0.4);">
                        📲 ENVIAR
                    </button>
                </a>
            </div>
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
