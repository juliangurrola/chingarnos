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

# Helper para añadir/quitar apuestas (CALLBACK MAS ROBUSTO)
def toggle_bet(desc, prob):
    if 'selected_bets' not in st.session_state:
        st.session_state['selected_bets'] = []
    
    current_bets = list(st.session_state['selected_bets'])
    exists = any(b['desc'] == desc for b in current_bets)
    
    if exists:
        st.session_state['selected_bets'] = [b for b in current_bets if b['desc'] != desc]
    else:
        st.session_state['selected_bets'] = current_bets + [{"desc": desc, "prob": prob}]

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

# --- SECCION LATERAL (SIDEBAR): TICKET DE APUESTAS AL PRINCIPIO ---
with st.sidebar:
    st.subheader("🛒 Tu Ticket")
    
    # Cálculos previos para el ticket
    display_odds = "0"
    payout = 0.0
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
            profit = wager * (combined_odds / 100.0) if combined_odds > 0 else wager * (100.0 / abs(combined_odds))
            payout = wager + profit
            st.metric("PAGO TOTAL", f"${payout:.2f}")
        
        msg = f"🎰 *MI PARLAY GANADOR* (Elven MX)\n\n"
        for b in st.session_state['selected_bets']: msg += f"• {b['desc']}\n"
        msg += f"\n*MOMIO:* {display_odds}\n*APUESTA:* ${wager:.2f}\n*PAGO:* ${payout:.2f}\n\n¡A cobrar! ⚾💸"
        wa_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
        
        st.markdown(f'''
            <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                <div style="width:100%; background: linear-gradient(90deg, #25D366, #128C7E); color:white; text-align:center; padding:18px; border-radius:15px; cursor:pointer; font-weight:bold; font-size:22px; box-shadow: 0 6px 20px rgba(37,211,102,0.4); margin-top:10px;">
                    📲 ENVIAR TICKET
                </div>
            </a>
        ''', unsafe_allow_html=True)
        
        if st.button("🗑️ Limpiar Ticket", key="clear_side"):
            st.session_state['selected_bets'] = []
            st.rerun()
    else:
        st.info("Selecciona jugadas para armar tu parlay.")

    st.markdown("---")
    st.header("⚙️ Opciones")
    st.caption("🚀 **VERSIÓN: PRO V2 (NEWS & LOGOS)**")
    
    if st.button("🔄 Actualizar Datos", key="update_side"):
        with st.spinner("Actualizando Inteligencia MLB..."):
            try:
                from scraper import fetch_daily_schedule
                from model import generate_predictions
                fetch_daily_schedule()
                generate_predictions()
                st.sidebar.success("¡Datos y Noticias actualizados!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

games_df = pd.DataFrame()
props_df = pd.DataFrame()
parlays_df = pd.DataFrame()
top_10_unified = []

conn = get_connection()
try:
    games_df = pd.read_sql_query('''
        SELECT d.game_id, d.game_date, d.home_team, d.home_team_id, d.away_team, d.away_team_id, 
               d.venue_name, d.weather_condition, d.temperature, d.wind_speed, d.wind_direction,
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
    
    # --- FILTRO MAESTRO RADICAL: CERO TOLERANCIA ---
    if not props_df.empty:
        bad_keywords = ["Bat", "Contacto", "Bateador", "Clave", "Cleanup", "4to"]
        # Eliminamos CUALQUIER COSA que contenga estas palabras, sin importar el ID
        pattern = '|'.join(bad_keywords)
        props_df = props_df[~props_df['player_name'].str.contains(pattern, case=False, na=False)]
    
    parlays_df = pd.read_sql_query('SELECT * FROM ai_parlays', conn)
    news_df = pd.read_sql_query('SELECT * FROM mlb_news', conn)
except:
    games_df = pd.DataFrame()
    props_df = pd.DataFrame()
    parlays_df = pd.DataFrame()
    news_df = pd.DataFrame()

# --- CREAR TOP 10 UNIFICADO (EQUIPOS + JUGADORES) ---
all_bets_list = []

# 1. Añadir jugadas de equipos (Moneyline / Totales)
if not games_df.empty:
    for _, row in games_df.iterrows():
        play_name = str(row.get('suggested_bet', 'N/A'))
        if "ML" in play_name:
            play_name = play_name.replace("ML", "Gana el Partido")
        
        all_bets_list.append({
            "type": "EQUIPO",
            "name": str(row.get('home_team', 'Partido')),
            "play": play_name,
            "conf": float(row.get('confidence_score', 0)),
            "odds": "VAR",
            "insight": str(row.get('key_insight', 'Análisis disponible.')),
            "p_id": 0,
            "t_id": row.get('home_team_id', 0)
        })

# 2. Añadir jugadas de jugadores (CON FILTRO DE SEGURIDAD)
if not props_df.empty:
    for _, row in props_df.iterrows():
        p_name = str(row.get('player_name', ''))
        
        # FILTRO DE SEGURIDAD FINAL (RUDO)
        bad_keywords = ["Bat", "Contacto", "Bateador", "Clave", "Cleanup", "4to"]
        if any(bad.lower() in p_name.lower() for bad in bad_keywords):
            continue
            
        all_bets_list.append({
            "type": "JUGADOR",
            "name": p_name,
            "play": f"{row.get('suggested_side', '')} {row.get('line', '')} {row.get('prop_type', '')}",
            "conf": float(row.get('confidence_score', 0)),
            "odds": str(row.get('american_odds', 'VAR')),
            "insight": str(row.get('key_insight', 'Proyección estadística.')),
            "p_id": row.get('player_id', 0),
            "t_id": 0
        })

# --- ALGORITMO DE BALANCE SHARP (TOP 10 DIVERSIFICADO) ---
# Clasificamos las apuestas por tipo de mercado popular en casinos
bet_categories = {
    "BATEO": [b for b in all_bets_list if "Hit" in b['play'] or "HR" in b['play'] or "Total Bases" in b['play'] or "BB" in b['play']],
    "EQUIPOS": [b for b in all_bets_list if "Gana el Partido" in b['play'] or "Carreras Totales" in b['play'] or "Runline" in b['play']],
    "PITCHEO": [b for b in all_bets_list if "Strikeouts" in b['play']]
}

# Tomamos los mejores de cada categoría para asegurar variedad
top_bateo = sorted(bet_categories["BATEO"], key=lambda x: x['conf'], reverse=True)[:4]
top_equipos = sorted(bet_categories["EQUIPOS"], key=lambda x: x['conf'], reverse=True)[:4]
top_pitcheo = sorted(bet_categories["PITCHEO"], key=lambda x: x['conf'], reverse=True)[:2]

# Unificamos y ordenamos el Top 10 final
top_10_unified = sorted(top_bateo + top_equipos + top_pitcheo, key=lambda x: x['conf'], reverse=True)

conn.close()

if games_df.empty:
    st.warning("⚠️ La base de datos está vacía en este servidor.")
    st.info("Por favor, haz clic en el botón **'🔄 Actualizar Datos'** en el menú de la izquierda para descargar las estadísticas de hoy y generar las predicciones.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 Top 10", "🤑 Parlays IA", "📝 Armador", "📊 Juegos", "🗞️ Noticias"])

# TAB 1: MEJORES APUESTAS
with tab1:
    st.subheader("🏆 TOP 10 SELECCIONES DE ELVEN MX")
    st.markdown("Lo más probable del día entre equipos y jugadores.")
    
    for i, bet in enumerate(top_10_unified):
        with st.container(border=True):
            col_img, col_info, col_action = st.columns([1, 3, 1])
            
            with col_img:
                if bet['type'] == "JUGADOR":
                    try:
                        p_id = int(float(bet['p_id']))
                        if p_id > 0:
                            st.image(f"https://img.mlbstatic.com/mlb-photos/person/{p_id}@3x.jpg", width=80)
                        else: st.markdown("<h1 style='text-align:center;'>⚾</h1>", unsafe_allow_html=True)
                    except:
                        st.markdown("<h1 style='text-align:center;'>⚾</h1>", unsafe_allow_html=True)
                else:
                    # LOGO DE EQUIPO OFICIAL
                    t_id = bet.get('t_id', 0)
                    if t_id > 0:
                        st.image(f"https://www.mlbstatic.com/team-logos/{t_id}.svg", width=80)
                    else:
                        st.markdown("<h1 style='text-align:center;'>🏟️</h1>", unsafe_allow_html=True)
            
            with col_info:
                st.markdown(f"<div style='font-size:20px; font-weight:bold; color:white;'>{bet['name']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:24px; font-weight:bold; color:#FF5722;'>{bet['play']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='background:#1A1C24; padding:5px; border-left:3px solid #4CAF50; font-size:12px; margin:5px 0;'>💡 {bet['insight']}</div>", unsafe_allow_html=True)
            
            with col_action:
                # PROBABILIDAD GIGANTE
                st.markdown(f"<div style='text-align:center; line-height:1;'><span style='font-size:32px; font-weight:bold; color:#4CAF50;'>{bet['conf']:.0f}%</span><br><span style='font-size:10px; opacity:0.6;'>PROB</span></div>", unsafe_allow_html=True)
                
                bet_desc = f"{bet['name']}: {bet['play']}"
                is_in = any(b['desc'] == bet_desc for b in st.session_state['selected_bets'])
                label = "✅ EN TICKET" if is_in else "➕ AÑADIR"
                
                if st.button(label, key=f"top10_v2_{i}_{bet['name']}", use_container_width=True):
                    toggle_bet(bet_desc, bet['conf'])
                    st.rerun()

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
                
                # Buscador de Jugadores
                search = st.text_input("🔍 Buscar jugador o apuesta:", key=f"search_{row['game_id']}")
                
                # Props
                game_props = props_df[props_df['game_id'] == row['game_id']]
                if search:
                    game_props = game_props[game_props['player_name'].str.contains(search, case=False) | 
                                            game_props['prop_type'].str.contains(search, case=False)]
                
                for idx, prop in game_props.iterrows():
                    with st.container(border=True):
                        c_img, c_det = st.columns([1, 4])
                        p_id = prop.get('player_id', 0)
                        with c_img:
                            if p_id > 0:
                                st.image(f"https://img.mlbstatic.com/mlb-photos/person/{p_id}@3x.jpg", width=60)
                            else:
                                st.markdown("### 🏟️")
                        with c_det:
                            desc_p = f"{prop['player_name']}: {prop['suggested_side']} {prop['line']} {prop['prop_type']}"
                            prob_p = prop['confidence_score']
                            if st.checkbox(f"**{desc_p}**", key=f"p_{prop['prop_id']}"):
                                if {"desc": desc_p, "prob": prob_p} not in st.session_state['selected_bets']: st.session_state['selected_bets'].append({"desc": desc_p, "prob": prob_p})
                            else:
                                if {"desc": desc_p, "prob": prob_p} in st.session_state['selected_bets']: st.session_state['selected_bets'].remove({"desc": desc_p, "prob": prob_p})
                            st.markdown(f"<span style='color:#2196F3; font-weight:bold;'>{prob_p:.1f}% Prob.</span> | Momio: {prop['american_odds']}", unsafe_allow_html=True)

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
                    st.markdown("**🌬️ Análisis de Campo:**")
                    w_icon = "🚩" if "Out" in row['wind_direction'] else "🏳️"
                    w_color = "#FF5252" if "Out" in row['wind_direction'] else "#448AFF"
                    st.markdown(f'''
                        <div style="background-color:#1A1C24; padding:10px; border-radius:10px; border-left: 5px solid {w_color};">
                            <div style="font-size:12px; color:gray;">CONDICIÓN</div>
                            <div style="font-size:16px; font-weight:bold;">☀️ {row['weather_condition']} ({row['temperature']}°F)</div>
                            <div style="font-size:12px; color:gray; margin-top:5px;">VIENTO</div>
                            <div style="font-size:16px; font-weight:bold;">{w_icon} {row['wind_speed']} mph, {row['wind_direction']}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                
                st.progress(int(row['home_win_prob']), text=f"Probabilidad de Local ({row['home_team']}): {row['home_win_prob']:.1f}%")
                st.metric("Carreras Totales Esperadas", f"{row['expected_total_runs']} carreras")
                
                with st.container(border=True):
                    st.markdown("#### 📌 Análisis de Referencia (Insights)")
                    st.info(row['key_insight'])

# TAB 5: NOTICIAS & TENDENCIAS
with tab5:
    st.subheader("🗞️ Últimas Noticias & Tendencias MLB")
    if 'news_df' in locals() and not news_df.empty:
        for _, item in news_df.iterrows():
            with st.container(border=True):
                st.markdown(f"### {item['title']}")
                st.caption(f"📅 {item['published']}")
                st.write(item['summary'])
                st.markdown(f"[Leer más en MLB.com]({item['link']})")
    else:
        st.info("No hay noticias recientes. Haz clic en 'Actualizar Datos' para cargar lo más nuevo.")
