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

# --- FUNZIONI DI SUPPORTO METEO ---
def get_weather_data(latitude, longitude):
    """Recupera i dati meteo attuali da Open-Meteo in base alle coordinate."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
    
    weather_codes = {
        0: "Cielo Sereno ☀️",
        1: "Prevalentemente Sereno 🌤️",
        2: "Parzialmente Nuvoloso ⛅",
        3: "Coperto ☁️",
        45: "Nebbia 🌫️",
        48: "Nebbia con Brina 🌫️",
        51: "Pioggerella Leggera 🌦️",
        61: "Pioggia Leggera 🌧️",
        63: "Pioggia Moderata 🌧️",
        65: "Pioggia Intensa 🌧️",
        80: "Rovesci di Pioggia 🌦️",
        95: "Temporale ⛈️"
    }

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "current_weather" in data:
            current = data["current_weather"]
            w_code = current.get("weathercode", 0)
            return {
                "temperature": current.get("temperature", "N/D"),
                "windspeed": current.get("windspeed", "N/D"),
                "condition": weather_codes.get(w_code, "Variabile 🌤️")
            }
        else:
            return None
    except Exception as e:
        st.error(f"Errore nel recupero dei dati meteo: {e}")
        return None

# --- INTERFACCIA UTENTE ---

# Titolo principale e Sincronizzazione
col_title, col_sync = st.columns([3, 1])
with col_title:
    st.markdown("# ☀️ Gestione Impianti & Report FusionSolar")

with col_sync:
    if st.button("🔄 Sincronizza Nuovi Impianti", use_container_width=True):
        st.info("Sincronizzazione avviata...")

st.markdown("---")

# 1. TABELLA PARAMETRI IMPIANTI
st.markdown("## 📋 Tabella Parametri Impianti")
st.markdown("Modifica i dati se necessario. I nuovi impianti aggiunti da Huawei appariranno in fondo senza cancellare le modifiche.")

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

# 2. SEZIONE METEO DEL GIORNO
st.markdown("## 🌤️ Previsioni Meteo del Giorno")
st.markdown("Inserisci le coordinate per visualizzare il meteo in tempo reale:")

c_lat, c_lon, c_btn = st.columns([2, 2, 1])

with c_lat:
    lat_val = st.number_input("Latitudine (°N)", value=45.81, format="%.2f", step=0.01)

with c_lon:
    lon_val = st.number_input("Longitudine (°E)", value=13.22, format="%.2f", step=0.01)

with c_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    check_weather = st.button("🌦️ Ottieni Meteo", use_container_width=True)

if check_weather:
    with st.spinner("Aggiornamento meteo in corso..."):
        w = get_weather_data(lat_val, lon_val)
        if w:
            m1, m2, m3 = st.columns(3)
            m1.metric("Stato del Tempo", w['condition'])
            m2.metric("Temperatura", f"{w['temperature']} °C")
            m3.metric("Velocità Vento", f"{w['windspeed']} km/h")
        else:
            st.warning("Nessun dato meteo trovato per queste coordinate.")

st.markdown("---")

# 3. PULSANTE ROSSO DI ESECUZIONE
if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
    st.success("Estrazione e generazione report avviate correttamente!")
