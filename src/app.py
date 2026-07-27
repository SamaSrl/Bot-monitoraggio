import pandas as pd
import requests
import datetime

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Gestione Impianti & Report FusionSolar",
    page_icon="☀️",
    layout="wide"
)

# --- SIDEBAR: CREDENZIALI API FUSIONSOLAR ---
st.sidebar.header("🔑 Credenziali API FusionSolar")
fs_userName = st.sidebar.text_input("Username API", value="")
fs_systemCode = st.sidebar.text_input("System Code / Password API", type="password", value="")

# --- API FUSIONSOLAR: AUTENTICAZIONE E RETRIEVAL DATI ---
def get_fusionsolar_token(username, system_code):
    """Richiede il token di sessione X-SRT all'API Huawei FusionSolar."""
    if not username or not system_code:
        return None
    
    url = "https://eu5.fusionsolar.huawei.com/thirdparty/login"
    payload = {"userName": username, "systemCode": system_code}
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                # Huawei restituisce il token nell'header 'X-SRT' o nel body
                return res.headers.get("X-SRT") or data.get("data")
    except Exception:
        pass
    return None

def get_fusionsolar_real_kpi(station_code, token):
    """
    Interroga l'API Huawei FusionSolar per recuperare la produzione reale odierna (day_power) in kWh.
    """
    if not token:
        return None

    url = "https://eu5.fusionsolar.huawei.com/thirdparty/getStationRealKpi"
    headers = {"Content-Type": "application/json", "X-SRT": token}
    payload = {"stationCodes": station_code}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                # Estrae day_power (espresso in kWh o MWh a seconda della versione dell'API)
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
    Recupera l'irraggiamento sul piano dei moduli tenendo conto della timezone locale
    per evitare lo sfasamento tra ore solari e ore locali.
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

            # Somma dell'energia oraria accumulata fino all'ora solare/locale corrente
            for h in range(current_hour):
                cumulative_poa += float(hourly_tilted[h]) if h < len(hourly_tilted) else 0.0

            val_current_hour = float(hourly_tilted[current_hour]) if current_hour < len(hourly_tilted) else 0.0
            cumulative_poa += val_current_hour * (current_minute / 60.0)
            current_hour_irr = val_current_hour
    except Exception:
        pass

    return round(cumulative_poa, 2), round(current_hour_irr, 2)

# --- INTERFACCIA UTENTE ---

st.markdown("# ☀️ Gestione Impianti & Report FusionSolar")
st.markdown("---")

# 1. TABELLA PARAMETRI IMPIANTI
st.markdown("## 📋 Tabella Parametri Impianti")

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

# 2. SEZIONE PERFORMANCE
st.markdown("## 📊 Performance Produzione Odierna (Attesa vs Reale API)")

if st.button("📈 Calcola Performance Odierna", type="secondary"):
    # Verifica autenticazione Huawei
    token = get_fusionsolar_token(fs_userName, fs_systemCode)
    if not token and (fs_userName or fs_systemCode):
        st.warning("⚠️ Impossibile autenticarsi su FusionSolar API. Verificare le credenziali nella barra laterale.")

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

            # 1. Calcolo Irraggiamento e Produzione Teorica
            cum_poa_wh, current_poa_w = get_poa_irradiance_data(lat, lon, tilt, azimuth, now)
            
            # PR di impianto medio standard: ~82-85%
            performance_ratio = 0.82
            prod_attesa = round(potenza * (cum_poa_wh / 1000.0) * performance_ratio, 2)

            # 2. Lettura Reale da API FusionSolar
            prod_reale_api = get_fusionsolar_real_kpi(st_code, token)

            if prod_reale_api is not None:
                prod_reale_display = prod_reale_api
                diff_perc = round(((prod_reale_api - prod_attesa) / prod_attesa) * 100, 2) if prod_attesa > 0 else 0.0
            else:
                prod_reale_display = "In attesa di Token API..."
                diff_perc = 0.0

            performance_list.append({
                "Nome Impianto": nome,
                "Potenza (kWp)": potenza,
                "Tilt / Azimut": f"{tilt}° / {azimuth}°",
                "Irraggiamento Istantaneo": f"{current_poa_w} W/m²",
                "Prod. Attesa Cumulata (kWh)": prod_attesa,
                "Prod. Reale API Huawei (kWh)": prod_reale_display,
                "Scostamento (%)": diff_perc
            })

        perf_df = pd.DataFrame(performance_list)
        st.dataframe(perf_df, use_container_width=True, hide_index=True)
