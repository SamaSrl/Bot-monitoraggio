import hashlib
import requests
import datetime
import pandas as pd
import streamlit as st

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Gestione Impianti & Report FusionSolar",
    page_icon="☀️",
    layout="wide"
)

# --- RECUPERO CREDENZIALI DA STREAMLIT SECRETS ---
def get_secret_credentials():
    """Estrae username e password/systemCode dai Secrets configurati su Streamlit Cloud."""
    username = (
        st.secrets.get("FUSIONSOLAR_USERNAME", None) 
        or st.secrets.get("USERNAME", None)
    )
    password = (
        st.secrets.get("FUSIONSOLAR_PASSWORD", None) 
        or st.secrets.get("PASSWORD", None) 
        or st.secrets.get("SYSTEM_CODE", None)
    )
    return username, password

# --- API FUSIONSOLAR: AUTENTICAZIONE NORTHBOUND ---
def get_fusionsolar_token(username, password):
    """
    Richiede il token di sessione X-SRT all'API Huawei FusionSolar Northbound API.
    Le API Huawei Northbound utilizzano la porta 27200 sui gateway dedicati.
    """
    if not username or not password:
        return None, None, "Username o Password mancanti nei Secrets di Streamlit."

    # Hashing MD5 della password se non è già formattata a 32 caratteri
    if len(str(password)) != 32:
        system_code = hashlib.md5(str(password).encode('utf-8')).hexdigest()
    else:
        system_code = str(password)

    # Gateway API ufficiali Huawei FusionSolar con porta 27200
    api_hosts = [
        "https://uni001eu5.fusionsolar.huawei.com:27200",
        "https://region01eu5.fusionsolar.huawei.com:27200",
        "https://eu5.fusionsolar.huawei.com"
    ]

    payload = {
        "userName": str(username).strip(),
        "systemCode": system_code
    }
    headers = {"Content-Type": "application/json"}

    error_logs = []

    for base_url in api_hosts:
        url = f"{base_url}/thirdparty/login"
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                try:
                    data = res.json()
                    if data.get("success"):
                        token = res.headers.get("X-SRT") or data.get("data")
                        return token, base_url, None
                    else:
                        fail_code = data.get("failCode", "N/D")
                        message = data.get("message", "Credenziali o SystemCode errati")
                        error_logs.append(f"{base_url} -> Codice {fail_code}: {message}")
                except ValueError:
                    error_logs.append(f"{base_url} -> Risposta non-JSON ricevuta")
            else:
                error_logs.append(f"{base_url} -> HTTP Status {res.status_code}")
        except requests.exceptions.RequestException as e:
            error_logs.append(f"{base_url} -> Errore Connessione: {str(e)}")

    return None, None, " | ".join(error_logs)

def get_fusionsolar_real_kpi(station_code, token, active_host):
    """
    Interroga l'API Huawei FusionSolar per recuperare la produzione reale odierna (day_power) in kWh.
    """
    if not token or not active_host:
        return None

    url = f"{active_host}/thirdparty/getStationRealKpi"
    headers = {"Content-Type": "application/json", "X-SRT": token}
    payload = {"stationCodes": station_code}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                kpi_list = data.get("data", [])
                for kpi in kpi_list:
                    if kpi.get("stationCode") == station_code:
                        data_dict = kpi.get("dataItemMap", {})
                        day_power = data_dict.get("day_power", 0.0)
                        return float(day_power)
    except Exception:
        pass
    return None

# --- OPEN-METEO: IRRAGGIAMENTO CORRETTO PER FUSO ORARIO ---
def get_poa_irradiance_data(lat, lon, tilt, azimuth_user, current_time):
    """
    Calcola l'irraggiamento inclinato cumulato (Wh/m²) e istantaneo (W/m²).
    Convenzione Azimut: 0° = SUD, 180° = NORD, -90°/270° = EST, 90° = OVEST.
    """
    azimuth_api = azimuth_user
    if azimuth_api > 180:
        azimuth_api -= 360

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=global_tilted_irradiance"
        f"&tilt={tilt}&azimuth={azimuth_api}"
        f"&timezone=auto&forecast_days=1"
    )

    cumulative_poa = 0.0
    current_hour_irr = 0.0
    current_hour = current_time.hour
    current_minute = current_time.minute

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            hourly_tilted = data.get("hourly", {}).get("global_tilted_irradiance", [0]*24)

            # Accumula l'irraggiamento orario fino all'ora precedente
            for h in range(current_hour):
                cumulative_poa += float(hourly_tilted[h]) if h < len(hourly_tilted) else 0.0

            # Aggiunge pro-quota i minuti dell'ora corrente
            val_current_hour = float(hourly_tilted[current_hour]) if current_hour < len(hourly_tilted) else 0.0
            cumulative_poa += val_current_hour * (current_minute / 60.0)
            current_hour_irr = val_current_hour
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

# --- INTERFACCIA UTENTE STREAMLIT ---

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
    'Potenza (kWp)': [200.0, 100.0, 150.0, 100.0, 50.0, 200.0, 1131.0],
    'Latitudine': [45.81, 46.16, 46.07, 46.16, 45.95, 45.88, 45.88],
    'Longitudine': [13.22, 12.7, 12.94, 12.7, 13.03, 13.12, 13.12],
    'Tilt (°)': [20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
    'Azimut (°)': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
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

# 3. SEZIONE PERFORMANCE (ATTESA VS REALE API)
st.markdown("## 📊 Performance Produzione Odierna (Attesa vs Reale API)")

if st.button("📈 Calcola Performance Odierna", type="secondary"):
    fs_user, fs_pass = get_secret_credentials()
    
    token, active_host = None, None
    if not fs_user or not fs_pass:
        st.error("⚠️ Credenziali FusionSolar non trovate nei Secrets di Streamlit! Verifica `FUSIONSOLAR_USERNAME` e `FUSIONSOLAR_PASSWORD`.")
    else:
        token, active_host, err_msg = get_fusionsolar_token(fs_user, fs_pass)
        if not token:
            st.error(f"❌ Impossibile ottenere il Token dalle API Huawei FusionSolar. Dettagli tentativi: {err_msg}")

    with st.spinner("Connessione alle API Huawei FusionSolar e calcolo irraggiamento..."):
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

            # 1. Calcolo Irraggiamento e Produzione Attesa
            cum_poa_wh, current_poa_w = get_poa_irradiance_data(lat, lon, tilt, azimuth, now)
            performance_ratio = 0.82
            prod_attesa = round(potenza * (cum_poa_wh / 1000.0) * performance_ratio, 2)

            # 2. Lettura Reale da API FusionSolar
            prod_reale_api = get_fusionsolar_real_kpi(st_code, token, active_host) if token else None

            if prod_reale_api is not None:
                prod_reale_display = prod_reale_api
                diff_perc = round(((prod_reale_api - prod_attesa) / prod_attesa) * 100, 2) if prod_attesa > 0 else 0.0
            else:
                prod_reale_display = "N/D (Errore API/Secret)"
                diff_perc = 0.0

            performance_list.append({
                "Nome Impianto": nome,
                "Potenza (kWp)": potenza,
                "Tilt / Azimut": f"{tilt}° / {azimuth}°",
                "Irraggiamento Piano Moduli": f"{current_poa_w} W/m²",
                "Prod. Attesa Cumulata (kWh)": prod_attesa,
                "Prod. Reale API Huawei (kWh)": prod_reale_display,
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

# 4. PULSANTE ESECUZIONE REPORT
if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
    st.success("Estrazione e generazione report avviate correttamente!")
