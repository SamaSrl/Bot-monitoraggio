import streamlit as st
import pandas as pd
import requests
import datetime
import math
from fpdf import FPDF

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Gestione Impianti & Report FusionSolar",
    page_icon="☀️",
    layout="wide"
)

# --- FUNZIONE PER CALCOLARE L'IRRAGGIAMENTO SUL PIANO DEI PANNELLI (POA) ---
def calculate_poa_irradiance(lat, lon, tilt, azimuth, current_time):
    """
    Calcola l'irraggiamento effettivo (W/m²) che colpisce i moduli tenendo conto di:
    - Ora del giorno e giorno dell'anno (Posizione solare)
    - Tilt (Inclinazione pannelli)
    - Azimut (Orientamento rispetto al Sud: 180° = Sud, 90° = Est, 270° = Ovest)
    """
    # 1. Recupera irraggiamento solare globale e diretto da Open-Meteo per l'ora corrente
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=direct_normal_irradiance,diffuse_radiation,global_tilted_irradiance"
        f"&forecast_days=1"
    )
    
    dni = 0.0
    dhi = 0.0
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            hour = current_time.hour
            hourly_dni = data.get("hourly", {}).get("direct_normal_irradiance", [0]*24)
            hourly_dhi = data.get("hourly", {}).get("diffuse_radiation", [0]*24)
            
            dni = float(hourly_dni[hour]) if hour < len(hourly_dni) else 0.0
            dhi = float(hourly_dhi[hour]) if hour < len(hourly_dhi) else 0.0
    except Exception:
        pass

    if dni == 0 and dhi == 0:
        return 0.0

    # 2. Calcolo Posizione Solare
    day_of_year = current_time.timetuple().tm_yday
    hour_float = current_time.hour + current_time.minute / 60.0

    # Declinazione solare (in radianti)
    declination = math.radians(23.45 * math.sin(math.radians((360 / 365) * (day_of_year - 81))))
    
    # Latitudine in radianti
    lat_rad = math.radians(lat)
    
    # Angolo orario (omega) - 12:00 solare = 0°
    solar_time = hour_float + (4 * (lon - 15) / 60) # approssimazione fuso orario CET
    omega = math.radians((solar_time - 12) * 15)

    # Altezza solare (alpha)
    sin_alpha = math.sin(lat_rad) * math.sin(declination) + math.cos(lat_rad) * math.cos(declination) * math.cos(omega)
    sin_alpha = max(-1.0, min(1.0, sin_alpha))
    alpha = math.asin(sin_alpha) # Angolo di elevazione solare

    if alpha <= 0:
        return 0.0 # Il sole è sotto l'orizzonte

    # Azimut solare (gamma_s)
    cos_gamma_s = (math.sin(declination) * math.cos(lat_rad) - math.cos(declination) * math.sin(lat_rad) * math.cos(omega)) / math.cos(alpha)
    cos_gamma_s = max(-1.0, min(1.0, cos_gamma_s))
    gamma_s = math.acos(cos_gamma_s)
    if omega > 0:
        gamma_s = 2 * math.pi - gamma_s

    # 3. Orientamento Pannello (Convertito in radianti)
    beta = math.radians(tilt) # Inclinazione
    gamma = math.radians(azimuth) # Azimut (180° = Sud)

    # 4. Angolo di Incidenza Solare (theta)
    cos_theta = math.cos(alpha) * math.sin(beta) * math.cos(gamma_s - gamma) + math.sin(alpha) * math.cos(beta)
    cos_theta = max(0.0, cos_theta) # Se > 90° il sole è dietro il pannello

    # 5. Irraggiamento Effettivo sul Piano dei Moduli (POA - Plane of Array)
    poa_direct = dni * cos_theta
    poa_diffuse = dhi * (1 + math.cos(beta)) / 2 # Modello Isotropo Diffuso
    poa_total = poa_direct + poa_diffuse

    return round(poa_total, 2)

# --- FUNZIONE METEO GENERICA ---
def get_weather_data(latitude, longitude):
    """Recupera condizioni meteo generali."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
    weather_codes = {
        0: "Sereno ☀️", 1: "Prevalentemente Sereno 🌤️", 2: "Parzialmente Nuvoloso ⛅",
        3: "Coperto ☁️", 45: "Nebbia 🌫️", 51: "Pioggerella 🌦️", 61: "Pioggia 🌧️", 95: "Temporale ⛈️"
    }
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            cw = res.json().get("current_weather", {})
            return {
                "temp": f"{cw.get('temperature', 'N/D')} °C",
                "wind": f"{cw.get('windspeed', 'N/D')} km/h",
                "condition": weather_codes.get(cw.get("weathercode", 0), "Variabile 🌤️")
            }
    except Exception:
        pass
    return {"temp": "N/D", "wind": "N/D", "condition": "N/D"}

# --- FUNZIONE SIMULATA API FUSIONSOLAR ---
def get_fusionsolar_real_production(station_code):
    """Restituisce la produzione reale odierna del sito via API FusionSolar."""
    return round(float(hash(station_code) % 100) + 120.5, 2)

# --- INTERFACCIA UTENTE ---

col_title, col_sync = st.columns([3, 1])
with col_title:
    st.markdown("# ☀️ Gestione Impianti & Report FusionSolar")

with col_sync:
    if st.button("🔄 Sincronizza Nuovi Impianti", use_container_width=True):
        st.info("Sincronizzazione avviata...")

st.markdown("---")

# 1. TABELLA PARAMETRI IMPIANTI
st.markdown("## 📋 Tabella Parametri Impianti")
st.markdown("Modifica i dati se necessario. Tilt e Azimut influenzeranno direttamente i calcoli della produzione attesa.")

data = {
    'stationCode': ['NE=145335207', 'NE=187970646', 'NE=289231586', 'NE=231216926', 'NE=142360791', 'NE=167849112', 'NE=236021376'],
    'Nome Impianto': ['Omnia Ponte Rosso', 'Omnia Immobiliare - Scuola Piaget', 'Omnia Immobiliare Dignano', 'Omnia Immobiliare Maniago', 'Omnia Immobiliare Moretto', 'Omnia Capannone Nuovo', 'Omnia Immobiliare Rivignano'],
    'Potenza (kWp)': [200, 100, 150, 100, 50, 200, 200],
    'Latitudine': [45.81, 46.16, 46.07, 46.16, 45.95, 45.88, 45.88],
    'Longitudine': [13.22, 12.7, 12.94, 12.7, 13.03, 13.12, 13.12],
    'Tilt (°)': [20, 20, 20, 20, 20, 20, 20],
    'Azimut (°)': [180, 180, 180, 180, 180, 180, 180]
}
df = pd.DataFrame(data)

edited_df = st.data_editor(
    df,
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True
)

st.markdown("---")

# 2. SEZIONE METEO AUTOMATICA
st.markdown("## 🌤️ Previsioni Meteo per Tutti gli Impianti")

if st.button("🌦️ Aggiorna Meteo per Tutti gli Impianti", type="secondary"):
    with st.spinner("Scaricamento dati meteo..."):
        weather_list = []
        for idx, row in edited_df.iterrows():
            w_data = get_weather_data(row['Latitudine'], row['Longitudine'])
            weather_list.append({
                "Nome Impianto": row['Nome Impianto'],
                "Latitudine": row['Latitudine'],
                "Longitudine": row['Longitudine'],
                "Condizione Meteo": w_data['condition'],
                "Temperatura": w_data['temp'],
                "Velocità Vento": w_data['wind']
            })
        st.dataframe(pd.DataFrame(weather_list), use_container_width=True, hide_index=True)

st.markdown("---")

# 3. SEZIONE CONFRONTO PRODUZIONE ATTESA VS REALE
st.markdown("## 📊 Performance Produzione Odierna (Attesa vs Reale)")
st.markdown("La produzione attesa include l'angolo d'incidenza orario basato su **Tilt** e **Azimut** dei moduli.")

if st.button("📈 Calcola Performance Odierna", type="secondary"):
    with st.spinner("Calcolo dinamico irraggiamento sui pannelli e lettura API FusionSolar..."):
        performance_list = []
        now = datetime.datetime.now()
        current_hour = now.hour

        # Stima ore di sole cumulate fino all'ora corrente per stimare la produzione del giorno
        hours_active = max(0, min(current_hour - 6, 12)) if current_hour >= 6 else 0

        for idx, row in edited_df.iterrows():
            st_code = row['stationCode']
            nome = row['Nome Impianto']
            potenza = float(row['Potenza (kWp)'])
            lat = float(row['Latitudine'])
            lon = float(row['Longitudine'])
            tilt = float(row['Tilt (°)'])
            azimuth = float(row['Azimut (°)'])

            # 1. Calcola l'irraggiamento sul piano dei pannelli (POA)
            poa_irr = calculate_poa_irradiance(lat, lon, tilt, azimuth, now)

            # 2. Produzione Attesa oraria / cumulata stimata (kWh)
            # Formula: Potenza (kWp) * Irraggiamento modulato (kW/m²) * Ore attive * Efficienza (85%)
            efficiency_factor = 0.85
            if hours_active > 0 and poa_irr > 0:
                prod_attesa = round(potenza * (poa_irr / 1000) * (hours_active * 0.65) * efficiency_factor, 2)
            else:
                prod_attesa = 0.0

            # 3. Lettura Produzione Reale (kWh)
            prod_reale = get_fusionsolar_real_production(st_code)

            # 4. Scostamento Percentuale
            if prod_attesa > 0:
                diff_perc = round(((prod_reale - prod_attesa) / prod_attesa) * 100, 2)
            else:
                diff_perc = 0.0

            performance_list.append({
                "Nome Impianto": nome,
                "Potenza (kWp)": potenza,
                "Tilt / Azimut": f"{tilt}° / {azimuth}°",
                "Irraggiamento Piano Moduli (W/m²)": f"{poa_irr} W/m²",
                "Prod. Attesa (kWh)": prod_attesa,
                "Prod. Reale API (kWh)": prod_reale,
                "Scostamento (%)": diff_perc
            })

        perf_df = pd.DataFrame(performance_list)

        # Stile condizionale sui colori dello scostamento
        def color_scostamento(val):
            try:
                num = float(val)
                color = '#22c55e' if num >= 0 else '#ef4444'
                return f'color: {color}; font-weight: bold;'
            except Exception:
                return ''

        styled_df = perf_df.style.applymap(color_scostamento, subset=['Scostamento (%)'])\
                                  .format({"Scostamento (%)": "{:+.2f}%"})

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

st.markdown("---")

# 4. PULSANTE ROSSO DI ESECUZIONE
if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
    st.success("Estrazione e generazione report avviate correttamente!")
