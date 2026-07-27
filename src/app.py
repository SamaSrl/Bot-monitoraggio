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
    url = f"{HUAWEI_BASE_URL}/login"
    headers = {"Content-Type": "application/json"}
    payload = {"username": username, "password": password}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                token = res.headers.get("X-SRT") or res.headers.get("xsrt")
                return token, None
            elif data.get("failCode") == 407:
                return None, "⏳ Limitazione frequenza Huawei (Rate limit: max 5 login/10 min). Attendi qualche minuto."
            else:
                return None, f"Errore Login: {data.get('message')} (Cod. {data.get('failCode')})"
        return None, f"Errore HTTP: {res.status_code}"
    except Exception as e:
        return None, f"Errore connessione Huawei: {e}"

def get_real_station_list(token):
    """Recupera la lista reale di tutti gli impianti associati all'account Northbound"""
    url = f"{HUAWEI_BASE_URL}/getStationList"
    headers = {"Content-Type": "application/json", "X-SRT": token}
    
    try:
        res = requests.post(url, json={}, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                return data.get("data"), None
            return [], f"Nessun impianto trovato: {data.get('message')}"
        return [], f"Errore HTTP Lista Impianti: {res.status_code}"
    except Exception as e:
        return [], f"Errore recupero stazioni: {e}"

def get_station_kpi(token, station_code):
    """Recupera i dati prestazionali (KPI) reali dell'impianto"""
    url = f"{HUAWEI_BASE_URL}/getStationRealKpi"
    headers = {"Content-Type": "application/json", "X-SRT": token}
    payload = {"stationCodes": station_code}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                kpi_list = data.get("data", [])
                if kpi_list:
                    return kpi_list[0].get("dataItemMap", {}), None
            return {}, f"KPI vuoti per {station_code}"
        return {}, f"Errore HTTP KPI: {res.status_code}"
    except Exception as e:
        return {}, f"Errore KPI: {e}"

# ==========================================
# 3. CALCOLO METEO & PRODUZIONE ATTESA
# ==========================================
def get_expected_production_now(lat, lon, tilt, azimuth_user, kwp, pr=0.85):
    now_italy = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    current_hour = now_italy.hour
    current_minute = now_italy.minute

    azimuth_api = azimuth_user
    if azimuth_api > 180:
        azimuth_api -= 360

    # Chiamata Open-Meteo per l'irraggiamento inclinato odierno
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
            hourly_tilted = data.get("hourly", {}).get("global_tilted_irradiance", [])

            if hourly_tilted:
                # Ore trascorse dalle 00:00 fino all'ora precedente
                for h in range(min(current_hour, len(hourly_tilted))):
                    if hourly_tilted[h] is not None:
                        cumulative_poa_wh += float(hourly_tilted[h])

                # Minuti dell'ora corrente
                if current_hour < len(hourly_tilted) and hourly_tilted[current_hour] is not None:
                    current_instant_w = float(hourly_tilted[current_hour])
                    cumulative_poa_wh += current_instant_w * (current_minute / 60.0)

    except Exception as e:
        st.warning(f"⚠️ Errore connessione Open-Meteo: {e}")

    psh = cumulative_poa_wh / 1000.0
    expected_kwh = kwp * psh * pr

    return {
        "cumulative_poa_wh": round(cumulative_poa_wh, 2),
        "current_instant_w": round(current_instant_w, 2),
        "expected_kwh": round(expected_kwh, 2)
    }

# ==========================================
# 4. SIDEBAR CONFIGURAZIONE
# ==========================================
st.sidebar.header("🔑 Credenziali FusionSolar API")
api_user = st.sidebar.text_input("Utente API", value="Monitoragg_api")
api_pass = st.sidebar.text_input("Password API", type="password")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parametri Performance & Pitch")
performance_ratio = st.sidebar.slider("Performance Ratio (PR)", min_value=0.70, max_value=0.95, value=0.85, step=0.01)
default_tilt = st.sidebar.number_input("Inclinazione di Default (Tilt °)", value=15)
default_azimuth = st.sidebar.number_input("Azimut di Default (0°=SUD)", value=0)

# ==========================================
# 5. DASHBOARD PRINCIPALE
# ==========================================
btn_fetch = st.button("🔄 Carica Impianti Reali & Aggiorna Dati", type="primary")

if btn_fetch:
    if not api_pass:
        st.error("Inserisci la password dell'utente API nella barra laterale.")
    else:
        with st.spinner("Connessione a Huawei FusionSolar in corso..."):
            token, err_login = login_huawei(api_user, api_pass)
        
        if err_login:
            st.error(err_login)
        else:
            st.success("✅ Autenticato con successo su Huawei!")
            
            # 1. Recupera la lista REALE degli impianti assegnati all'utente
            with st.spinner("Download lista impianti reali da Huawei..."):
                stations, err_stations = get_real_station_list(token)

            if err_stations or not stations:
                st.error(f"Impossibile recuperare gli impianti: {err_stations}")
            else:
                now_str = datetime.datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y - %H:%M:%S")
                st.info(f"🕒 Ultimo aggiornamento: **{now_str}** | Trovati **{len(stations)}** impianti reali!")

                results = []
                progress_bar = st.progress(0)

                for idx, station in enumerate(stations):
                    s_code = station.get("stationCode")
                    s_name = station.get("stationName", "Impianto Sconosciuto")
                    
                    # Potenza nominale dell'impianto fornita da Huawei (in kW)
                    kwp = float(station.get("capacity", 0.0))
                    
                    # Coordinate geografiche dall'impianto Huawei (con fallback su Italia Nord-Est)
                    lat = float(station.get("latitude")) if station.get("latitude") else 46.06
                    lon = float(station.get("longitude")) if station.get("longitude") else 13.23

                    # 2. Recupero Produzione Reale da Huawei
                    kpi_map, _ = get_station_kpi(token, s_code)
                    real_kwh = float(kpi_map.get("day_power", 0.0)) if kpi_map else 0.0
                    active_kw = float(kpi_map.get("active_power", 0.0)) if kpi_map else 0.0

                    # 3. Calcolo Meteo e Produzione Attesa per le coordinate reali
                    meteo = get_expected_production_now(
                        lat=lat,
                        lon=lon,
                        tilt=default_tilt,
                        azimuth_user=default_azimuth,
                        kwp=kwp,
                        pr=performance_ratio
                    )

                    expected_kwh = meteo["expected_kwh"]
                    perf_ratio = round((real_kwh / expected_kwh * 100), 1) if expected_kwh > 0 else 0.0

                    results.append({
                        "Impianto": s_name,
                        "Codice Stazione": s_code,
                        "Potenza (kWp)": kwp,
                        "Potenza Istantanea (kW)": active_kw,
                        "Produzione Reale (kWh)": real_kwh,
                        "Produzione Attesa (kWh)": expected_kwh,
                        "Performance (%)": perf_ratio,
                        "Irraggiamento (W/m²)": meteo["current_instant_w"],
                        "Irraggiamento Cum. (Wh/m²)": meteo["cumulative_poa_wh"]
                    })

                    progress_bar.progress((idx + 1) / len(stations))

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
                st.markdown("### 🏢 Dettaglio Impianti Reali")

                def color_performance(val):
                    if val >= 95.0:
                        color = '#d4edda'
                    elif val >= 80.0:
                        color = '#fff3cd'
                    else:
                        color = '#f8d7da'
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
