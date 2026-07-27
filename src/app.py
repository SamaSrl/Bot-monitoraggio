import streamlit as st
import pandas as pd
import requests
import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 1. CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="FusionSolar - Monitor & Produzione Attesa",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ FusionSolar - Monitor In Tempo Reale")
st.caption("Confronto Produzione Reale Huawei vs Produzione Stimata (Open-Meteo)")

# ==========================================
# 2. FUNZIONI API HUAWEISOLAR (PVMS v1)
# ==========================================
HUAWEI_BASE_URL = "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1"

def login_huawei(username, password):
    """
    Effettua il login sulle API OpenAPI PVMS v1 di Huawei FusionSolar.
    Restituisce il token X-SRT dagli header della risposta HTTP.
    """
    url = f"{HUAWEI_BASE_URL}/login"
    headers = {"Content-Type": "application/json"}
    payload = {
        "username": username,
        "password": password  # Password in chiaro per OpenAPI PVMS v1
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                # Recupera il token X-SRT dagli header (case-insensitive)
                token = res.headers.get("X-SRT") or res.headers.get("xsrt")
                return token, None
            elif data.get("failCode") == 407:
                return None, "⏳ Limitazione frequenza Huawei (Rate limit: max 5 login/10 min). Attendi qualche minuto."
            else:
                return None, f"Errore Login Huawei: {data.get('message')} (Codice {data.get('failCode')})"
        else:
            return None, f"Errore Server HTTP: {res.status_code}"
    except Exception as e:
        return None, f"Errore connessione Huawei: {e}"

def get_station_kpi(token, station_code):
    """
    Recupera i dati prestazionali (KPI) dell'impianto, compresa la produzione
    giornaliera cumulata fino al momento della chiamata (day_power).
    """
    url = f"{HUAWEI_BASE_URL}/getStationRealKpi"
    headers = {
        "Content-Type": "application/json",
        "X-SRT": token
    }
    payload = {"stationCodes": station_code}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                kpi_list = data.get("data", [])
                if kpi_list:
                    return kpi_list[0].get("dataItemMap", {}), None
            return None, f"Impossibile leggere KPI per la stazione {station_code}"
        return None, f"Errore HTTP KPI: {res.status_code}"
    except Exception as e:
        return None, f"Errore durante il recupero KPI: {e}"

# ==========================================
# 3. CALCOLO PRODUZIONE ATTESA (OPEN-METEO)
# ==========================================
def get_expected_production_now(lat, lon, tilt, azimuth_user, kwp, pr=0.85):
    """
    Calcola l'irraggiamento cumulato (Wh/m²) e la produzione attesa (kWh)
    dalle 00:00 di oggi fino al MINUTO ESATTO dell'esecuzione.
    """
    # Fuso orario italiano nativo senza pytz
    now_italy = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    
    current_hour = now_italy.hour
    current_minute = now_italy.minute

    # Conversione Azimut per Open-Meteo (0° = SUD, -90° = EST, 90° = OVEST)
    azimuth_api = azimuth_user
    if azimuth_api > 180:
        azimuth_api -= 360

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=global_tilted_irradiance"
        f"&tilt={tilt}&azimuth={azimuth_api}"
        f"&timezone=Europe%2FRome&forecast_days=1"
    )

    cumulative_poa_wh = 0.0
    current_instant_w = 0.0

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            hourly_tilted = data.get("hourly", {}).get("global_tilted_irradiance", [0]*24)

            # Somma delle ore intere trascorse (00:00 -> Ora precedente)
            for h in range(current_hour):
                if h < len(hourly_tilted) and hourly_tilted[h] is not None:
                    cumulative_poa_wh += float(hourly_tilted[h])

            # Integrazione pro-quota dei minuti dell'ora corrente
            if current_hour < len(hourly_tilted) and hourly_tilted[current_hour] is not None:
                current_instant_w = float(hourly_tilted[current_hour])
                cumulative_poa_wh += current_instant_w * (current_minute / 60.0)

    except Exception as e:
        st.warning(f"Errore recupero meteo: {e}")

    # Calcolo Produzione Attesa: kWp * (Wh/m² / 1000) * PR
    psh = cumulative_poa_wh / 1000.0
    expected_kwh = kwp * psh * pr

    return {
        "cumulative_poa_wh": round(cumulative_poa_wh, 2),
        "current_instant_w": round(current_instant_w, 2),
        "expected_kwh": round(expected_kwh, 2),
        "timestamp": now_italy.strftime("%H:%M:%S")
    }

# ==========================================
# 4. SIDEBAR - CREDENZIALI E IMPIANTI
# ==========================================
st.sidebar.header("🔑 Credenziali FusionSolar API")
api_user = st.sidebar.text_input("Utente API", value="Monitoragg_api")
api_pass = st.sidebar.text_input("Password API", type="password")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parametri Performance")
performance_ratio = st.sidebar.slider("Performance Ratio (PR)", min_value=0.70, max_value=0.95, value=0.85, step=0.01)

# Tabella degli Impianti configurati
st.sidebar.markdown("---")
st.sidebar.subheader("📋 Lista Impianti")

plants_data = [
    {"Name": "Omnia Immobiliare Moretto", "StationCode": "NE=12345601", "kWp": 99.8, "Lat": 46.06, "Lon": 13.23, "Tilt": 15, "Azimuth": 0},
    {"Name": "Omnia Steni Spilimbergo",  "StationCode": "NE=12345602", "kWp": 49.5, "Lat": 46.11, "Lon": 12.90, "Tilt": 10, "Azimuth": -15},
    {"Name": "Omnia Uffici",             "StationCode": "NE=12345603", "kWp": 20.0, "Lat": 46.05, "Lon": 13.24, "Tilt": 30, "Azimuth": 0},
]

plants_df = pd.DataFrame(plants_data)
st.sidebar.dataframe(plants_df[["Name", "kWp"]], use_container_width=True)

# ==========================================
# 5. DASHBOARD PRINCIPALE
# ==========================================
btn_fetch = st.button("🔄 Aggiorna Dati In Tempo Reale", type="primary")

if btn_fetch:
    if not api_pass:
        st.error("Inserisci la password dell'utente API nella barra laterale.")
    else:
        with st.spinner("Autenticazione su Huawei FusionSolar in corso..."):
            token, err = login_huawei(api_user, api_pass)
        
        if err:
            st.error(err)
        else:
            st.success("✅ Autenticazione API eseguita con successo!")
            
            now_str = datetime.datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y - %H:%M:%S")
            st.info(f"🕒 Ultimo aggiornamento: **{now_str}**")

            results = []

            progress_bar = st.progress(0)
            for idx, plant in enumerate(plants_data):
                # 1. Recupero dati reali Huawei
                kpi_map, err_kpi = get_station_kpi(token, plant["StationCode"])
                
                # 'day_power' rappresenta la produzione kWh odierna fino all'ora corrente
                real_kwh = float(kpi_map.get("day_power", 0.0)) if kpi_map else 0.0
                active_power_kw = float(kpi_map.get("active_power", 0.0)) if kpi_map else 0.0

                # 2. Calcolo Produzione Attesa ad ORA
                meteo_data = get_expected_production_now(
                    lat=plant["Lat"],
                    lon=plant["Lon"],
                    tilt=plant["Tilt"],
                    azimuth_user=plant["Azimuth"],
                    kwp=plant["kWp"],
                    pr=performance_ratio
                )

                expected_kwh = meteo_data["expected_kwh"]

                # 3. Calcolo % Performance
                perf_ratio = round((real_kwh / expected_kwh * 100), 1) if expected_kwh > 0 else 0.0

                results.append({
                    "Impianto": plant["Name"],
                    "Potenza (kWp)": plant["kWp"],
                    "Potenza Istantanea (kW)": active_power_kw,
                    "Produzione Reale (kWh)": real_kwh,
                    "Produzione Attesa (kWh)": expected_kwh,
                    "Performance (%)": perf_ratio,
                    "Irraggiamento (W/m²)": meteo_data["current_instant_w"],
                    "Irraggiamento Cum. (Wh/m²)": meteo_data["cumulative_poa_wh"]
                })

                progress_bar.progress((idx + 1) / len(plants_data))

            df_res = pd.DataFrame(results)

            # --- KPI GLOBALI ---
            st.markdown("### 📊 Riepilogo Complessivo")
            col1, col2, col3, col4 = st.columns(4)
            
            tot_real = round(df_res["Produzione Reale (kWh)"].sum(), 2)
            tot_exp = round(df_res["Produzione Attesa (kWh)"].sum(), 2)
            avg_perf = round((tot_real / tot_exp * 100), 1) if tot_exp > 0 else 0.0
            tot_power = round(df_res["Potenza Istantanea (kW)"].sum(), 2)

            col1.metric("Produzione Reale Totale", f"{tot_real} kWh")
            col2.metric("Produzione Attesa Totale", f"{tot_exp} kWh")
            col3.metric("Efficienza Complessiva", f"{avg_perf} %")
            col4.metric("Potenza Istantanea Totale", f"{tot_power} kW")

            # --- TABELLA DETTAGLIATA ---
            st.markdown("### 🏢 Dettaglio Singoli Impianti")

            def color_performance(val):
                if val >= 95.0:
                    color = '#d4edda' # verde chiaro
                elif val >= 80.0:
                    color = '#fff3cd' # giallo chiaro
                else:
                    color = '#f8d7da' # rosso chiaro
                return f'background-color: {color}'

            styled_df = df_res.style.map(color_performance, subset=['Performance (%)'])\
                                   .format({
                                       "Potenza (kWp)": "{:.1f}",
                                       "Potenza Istantanea (kW)": "{:.2f}",
                                       "Produzione Reale (kWh)": "{:.2f}",
                                       "Produzione Attesa (kWh)": "{:.2f}",
                                       "Performance (%)": "{:.1f}%",
                                       "Irraggiamento (W/m²)": "{:.1f}",
                                       "Irraggiamento Cum. (Wh/m²)": "{:.1f}"
                                   })

            st.dataframe(styled_df, use_container_width=True)
