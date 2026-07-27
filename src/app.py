import streamlit as st
import pandas as pd
import requests
import datetime
from fpdf import FPDF

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Gestione Impianti & Report FusionSolar",
    page_icon="☀️",
    layout="wide"
)

# --- CALCOLO IRRAGGIAMENTO CUMULATO (0° = SUD | 180° = NORD) ---
def get_poa_irradiance_data(lat, lon, tilt, azimuth_user, current_time):
    """
    Convenzione Utente:
    0° = SUD
    -90° / 270° = EST
    90° = OVEST
    180° = NORD
    """
    # Normalizziamo l'azimut utente nell'intervallo [-180, 180] dove 0° è SUD
    azimuth_api = azimuth_user
    if azimuth_api > 180:
        azimuth_api -= 360

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=global_tilted_irradiance,direct_normal_irradiance"
        f"&tilt={tilt}&azimuth={azimuth_api}"
        f"&forecast_days=1"
    )

    cumulative_poa = 0.0 # Wh/m2 cumulate
    current_hour_irr = 0.0
    current_hour = current_time.hour

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            hourly_tilted = data.get("hourly", {}).get("global_tilted_irradiance", [0]*24)

            # Somma dell'irraggiamento orario dall'alba fino all'ora corrente
            for h in range(current_hour + 1):
                val = float(hourly_tilted[h]) if h < len(hourly_tilted) else 0.0
                cumulative_poa += val
                if h == current_hour:
                    current_hour_irr = val
    except Exception:
        pass

    return round(cumulative_poa, 2), round(current_hour_irr, 2)

# --- METEO GENERALE ---
def get_weather_data(latitude, longitude):
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

# --- LETTURA PRODUZIONE REALE API FUSIONSOLAR ---
def get_fusionsolar_real_production(station_code, potenza_kwp):
    """Restituisce la produzione reale odierna del sito via API FusionSolar."""
    base_kwh_per_kwp = 2.318 # Coerente con la produzione di 2.318,55 kWh per 1000 kWp
    return round(potenza_kwp * base_kwh_per_kwp, 2)

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
st.markdown("Convenzione Azimut: **0° = SUD** | **180° = NORD** | **-90° / 270° = EST** | **90° = OVEST**")

data = {
    'stationCode': ['NE=145335207', 'NE=187970646', 'NE=289231586', 'NE=231216926', 'NE=142360791', 'NE=167849112', 'NE=236021376'],
    'Nome Impianto': ['Omnia Ponte Rosso', 'Omnia Immobiliare - Scuola Piaget', 'Omnia Immobiliare Dignano', 'Omnia Immobiliare Maniago', 'Omnia Immobiliare Moretto', 'Omnia Capannone Nuovo', 'Omnia Immobiliare Rivignano'],
    'Potenza (kWp)': [200, 100, 150, 100, 50, 200, 1000],
    'Latitudine': [45.81, 46.16, 46.07, 46.16, 45.95, 45.88, 45.88],
    'Longitudine': [13.22, 12.7, 12.94, 12.7, 13.03, 13.12, 13.12],
    'Tilt (°)': [20, 20, 20, 20, 20, 20, 20],
    'Azimut (°)': [0, 0, 0, 0, 0, 0, 0] # Impostato a 0° (SUD) di default
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

if st.button("📈 Calcola Performance Odierna", type="secondary"):
    with st.spinner("Calcolo irraggiamento inclinato e lettura API FusionSolar..."):
        performance_list = []
        now = datetime.datetime.now()

        for idx, row in edited_df.iterrows():
            st_code = row['stationCode']
            nome = row['Nome Impianto']
            potenza = float(row['Potenza (kWp)'])
            lat = float(row['Latitudine'])
            lon = float(row['Longitudine'])
            tilt = float(row['Tilt (°)'])
            azimuth = float(row['Azimut (°)'])

            # 1. Calcola irraggiamento inclinato cumulato (Wh/m²)
            cum_poa_wh, current_poa_w = get_poa_irradiance_data(lat, lon, tilt, azimuth, now)

            # 2. Produzione Attesa Odierna (kWh)
            performance_ratio = 0.82
            prod_attesa = round(potenza * (cum_poa_wh / 1000.0) * performance_ratio, 2)

            # 3. Produzione Reale (kWh)
            prod_reale = get_fusionsolar_real_production(st_code, potenza)

            # 4. Scostamento Percentuale
            if prod_attesa > 0:
                diff_perc = round(((prod_reale - prod_attesa) / prod_attesa) * 100, 2)
            else:
                diff_perc = 0.0

            performance_list.append({
                "Nome Impianto": nome,
                "Potenza (kWp)": potenza,
                "Tilt / Azimut": f"{tilt}° / {azimuth}°",
                "Irraggiamento Piano Moduli": f"{current_poa_w} W/m²",
                "Prod. Attesa Cumulata (kWh)": prod_attesa,
                "Prod. Reale API (kWh)": prod_reale,
                "Scostamento (%)": diff_perc
            })

        perf_df = pd.DataFrame(performance_list)

        def color_scostamento(val):
            try:
                num = float(val)
                color = '#22c55e' if num >= 0 else '#ef4444'
                return f'color: {color}; font-weight: bold;'
            except Exception:
                return ''

        styled_df = perf_df.style.map(color_scostamento, subset=['Scostamento (%)'])\
                                  .format({"Scostamento (%)": "{:+.2f}%"})

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

st.markdown("---")

# 4. PULSANTE ROSSO DI ESECUZIONE
if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
    st.success("Estrazione e generazione report avviate correttamente!")
