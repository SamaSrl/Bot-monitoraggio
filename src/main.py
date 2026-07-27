import streamlit as st
import pandas as pd
import requests
import datetime

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Gestione Impianti & Report FusionSolar",
    page_icon="☀️",
    layout="wide"
)

# --- FUNZIONI DI SUPPORTO ---

def get_weather_data(latitude, longitude):
    """Recupera i dati meteo attuali da Open-Meteo per le coordinate date."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
    
    # Mappa dei codici meteo WMO per descrizioni in italiano
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
        response.raise_for_status() # Controlla se la richiesta è andata a buon fine
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
    except requests.exceptions.RequestException as e:
        st.error(f"Errore nel recupero dei dati meteo: {e}")
        return None

# --- INIZIO UI STREAMLIT ---

# Titolo principale e Sincronizzazione (come da screenshot)
col_title, col_sync = st.columns([3, 1])
with col_title:
    st.markdown("# ☀️ Gestione Impianti & Report FusionSolar")

with col_sync:
    # Pulsante per sincronizzare i nuovi impianti
    if st.button("🔄 Sincronizza Nuovi Impianti", use_container_width=True):
        st.info("Funzione di sincronizzazione in fase di sviluppo...")
        # Aggiungi qui la logica di sincronizzazione da Huawei se necessario

st.markdown("---") # Linea di separazione

# --- SEZIONE 1: TABELLA PARAMETRI IMPIANTI (come da screenshot) ---
st.markdown("## 📋 Tabella Parametri Impianti")
st.markdown("Modifica i dati se necessario. I nuovi impianti aggiunti da Huawei appariranno in fondo senza cancellare le modifiche.")

# Dati di esempio (basati sullo screenshot)
# In produzione, questi verrebbero caricati da un file CSV o database
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

# Visualizzazione della tabella modificabile (data editor)
edited_df = st.data_editor(
    df,
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True
)

# Pulsante per salvare le modifiche della tabella
if st.button("💾 Salva Modifiche Tabella", type="secondary"):
    st.success("Modifiche della tabella salvate correttamente (temporaneamente in memoria).")
    # In produzione, qui salveresti 'edited_df' su file (es. CSV)

st.markdown("---") # Linea di separazione

# --- SEZIONE 2: NUOVA SEZIONE METEO DINAMICA (Sotto la tabella) ---
st.markdown("## 🌤️ Meteo del Giorno per Coordinate Manuali")
st.markdown("Inserisci le coordinate geografiche (Latitudine e Longitudine) del luogo per ottenere le previsioni meteo aggiornate.")

# Usa delle colonne per gli input e il pulsante, più compatto
col_lat, col_lon, col_btn = st.columns([2, 2, 1])

with col_lat:
    # Input numero per la latitudine (valori predefiniti di esempio)
    lat_input = st.number_input("Latitudine (°N)", value=45.81, format="%.2f", step=0.01)

with col_lon:
    # Input numero per la longitudine (valori predefiniti di esempio)
    lon_input = st.number_input("Longitudine (°E)", value=13.22, format="%.2f", step=0.01)

with col_btn:
    st.markdown("<br>", unsafe_allow_html=True) # Spaziatura per allineare il pulsante
    # Pulsante per ottenere il meteo per le coordinate inserite
    get_weather_btn = st.button("🌦️ Ottieni Meteo", use_container_width=True)

# Contenitore per i risultati del meteo
weather_container = st.container()

# Logica per recuperare e mostrare i dati al clic del pulsante
if get_weather_btn:
    with st.spinner("Recupero dati meteo in corso..."):
        weather_results = get_weather_data(lat_input, lon_input)
        
        with weather_container:
            if weather_results:
                st.markdown("### Dati Meteo Attuali")
                # Creazione di card meteo usando le colonne
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.metric("Stato del Tempo", weather_results['condition'])
                with c2:
                    st.metric("Temperatura", f"{weather_results['temperature']} °C")
                with c3:
                    st.metric("Velocità Vento", f"{weather_results['windspeed']} km/h")
                
                st.caption(f"Dati meteo per Lat: {lat_input:.2f}, Lon: {lon_input:.2f} aggiornati al {datetime.datetime.now().strftime('%H:%M:%S')}")
            else:
                st.warning("Non è stato possibile recuperare i dati meteo per le coordinate inserite.")

st.markdown("---") # Linea di separazione

# --- SEZIONE 3: PULSANTE RUN (come da screenshot) ---
# Pulsante rosso grande per avviare il report principale
st.markdown("<br>", unsafe_allow_html=True) # Spaziatura aggiuntiva
if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
    # In produzione, qui andrebbe la logica principale di FusionSolar
    st.info("Funzione di estrazione dati e generazione report in fase di sviluppo...")
    st.success(f"Report per ieri ({datetime.date.today() - datetime.timedelta(days=1)}) generato correttamente (esempio).")
