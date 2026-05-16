import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from database import get_connection, init_db

# Inicializar DB si no existe (importante para la nube)
init_db()

st.set_page_config(page_title="A chingarnos al casino x Elven", page_icon="🤑", layout="wide")

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

# UI PRINCIPAL (LOGO ELVEN)
col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        st.image("elven_logo.jpg", use_container_width=True)
    except:
        pass
with col_title:
    st.title("🤑 A chingarnos al casino x Elven")
    st.markdown("Sistema avanzado con **Armador de Parlays**, **Player Props** y **Calculadora de Ganancias**.")

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
               p.expected_total_runs, p.suggested_bet, p.confidence_score
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
    for i, (_, row) in enumerate(best_props.iterrows()):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"<h4 style='margin-bottom:0;'>{row['player_name']}</h4>", unsafe_allow_html=True)
                st.markdown(f"**{row['suggested_side']} {row['line']} {row['prop_type']}**")
                st.markdown(f"Momio: **{row['american_odds']}**")
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
        
    for i, row in games_df.iterrows():
        with st.expander(f"🏟️ {row['away_team']} @ {row['home_team']}", expanded=False):
            st.markdown("#### 🏆 Ganador del Partido")
            col1, col2 = st.columns(2)
            
            # Bet 1: ML Home
            desc_h = f"{row['home_team']} ML"
            prob_h = row['home_win_prob']
            with col1:
                with st.container(border=True):
                    if st.checkbox(f"**{desc_h}**", key=f"h_{row['game_id']}"):
                        if {"desc": desc_h, "prob": prob_h} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_h, "prob": prob_h})
                    else:
                        if {"desc": desc_h, "prob": prob_h} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_h, "prob": prob_h})
                    st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_h:.1f}%</h3>", unsafe_allow_html=True)
                    
            # Bet 2: ML Away
            desc_a = f"{row['away_team']} ML"
            prob_a = row['away_win_prob']
            with col2:
                with st.container(border=True):
                    if st.checkbox(f"**{desc_a}**", key=f"a_{row['game_id']}"):
                        if {"desc": desc_a, "prob": prob_a} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_a, "prob": prob_a})
                    else:
                        if {"desc": desc_a, "prob": prob_a} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_a, "prob": prob_a})
                    st.markdown(f"<h3 style='color:#4CAF50; margin-top:-10px;'>{prob_a:.1f}%</h3>", unsafe_allow_html=True)

            st.markdown("#### ⚾ Jugadas y Props")
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

    # Sidebar recipt
    st.sidebar.markdown("### 🛒 Tu Recibo de Apuesta")
    wager = st.sidebar.number_input("Monto a apostar ($):", min_value=10.0, value=100.0, step=10.0)
    
    if len(st.session_state['selected_bets']) == 0:
        st.sidebar.write("No has seleccionado ninguna apuesta.")
    else:
        probs = []
        for b in st.session_state['selected_bets']:
            st.sidebar.write(f"- {b['desc']}")
            probs.append(b['prob'])
            
        combined_odds = calc_parlay_odds(probs)
        
        if combined_odds == "N/A":
            st.sidebar.error("Error calculando momio.")
        else:
            display_odds = f"+{combined_odds}" if combined_odds > 0 else f"{combined_odds}"
            st.sidebar.success(f"**MOMIO DEL PARLAY:** {display_odds}")
            
            # Calcular ganancia
            if combined_odds > 0:
                profit = wager * (combined_odds / 100.0)
            else:
                profit = wager * (100.0 / abs(combined_odds))
                
            payout = wager + profit
            st.sidebar.markdown(f"### 💰 Posible Ganancia")
            st.sidebar.metric(label="Pago Total", value=f"${payout:.2f}", delta=f"+${profit:.2f} ganancia")
            
            # BOTON WHATSAPP
            msg = f"🎰 *MI PARLAY GANADOR* (A chingarnos al casino x Elven)\n\n"
            for b in st.session_state['selected_bets']:
                msg += f"• {b['desc']}\n"
            msg += f"\n*MOMIO:* {display_odds}\n"
            msg += f"*APUESTA:* ${wager:.2f}\n"
            msg += f"*PAGO ESTIMADO:* ${payout:.2f}\n\n"
            msg += "¡A cobrar! ⚾💸"
            
            encoded_msg = urllib.parse.quote(msg)
            wa_url = f"https://wa.me/?text={encoded_msg}"
            
            st.sidebar.markdown(f'''
                <a href="{wa_url}" target="_blank">
                    <button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; cursor:pointer; font-weight:bold;">
                        📲 Enviar por WhatsApp
                    </button>
                </a>
            ''', unsafe_allow_html=True)

# TAB 4: JUEGOS PRINCIPALES
with tab4:
    st.subheader("📊 Análisis de Todos los Partidos")
    for _, row in games_df.iterrows():
        with st.expander(f"{row['away_team']} vs {row['home_team']} - {row['venue_name']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Pitchers Abridores:**")
                st.write(f"🏠 {row['home_team']}: {row['home_pitcher_name']}")
                st.write(f"✈️ {row['away_team']}: {row['away_pitcher_name']}")
            with col2:
                st.markdown("**Condiciones (Estadio/Clima):**")
                st.write(f"🌤️ {row['weather_condition']}")
                st.write(f"💨 Viento: {row['wind_speed']} mph, {row['wind_direction']}")
            
            st.progress(int(row['home_win_prob']), text=f"Probabilidad de Local ({row['home_team']}): {row['home_win_prob']:.1f}%")
            st.metric("Carreras Totales Esperadas", f"{row['expected_total_runs']} carreras")
