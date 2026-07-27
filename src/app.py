import streamlit as st
import pandas as pd
import requests
import datetime
import time
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
# 2. RECUPERO SECRETS (FLESSIBILE)
# ==========================================
API_USER = (
    st.secrets.get("huawei", {}).get("username")
    or st.secrets.get("username")
    or st.secrets.get("FUSIONSOLAR_USERNAME", "Monitoragg_api")
)

API_PASS = (
    st.secrets.get("huawei", {}).get("password")
    or st.secrets.get("password")
    or st.secrets.get("FUSIONSOLAR_PASSWORD", "")
)

if not API_PASS:
    st.error("⚠️ Password non trovata nei Secrets di Streamlit!")

# ==========================================
# 3. FUNZIONI API HUAWEISOLAR CON CACHE
# ==========================================
HUAWEI_BASE_URL = "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1"

@st.cache_data(ttl=500, show_spinner=False)
def get_huawei_token_cached(username, password):
    """
    Effettua il login e salva il token in CACHE per ~8 minuti (480s).
    Questo EVITA l'errore 'Interface access frequency:5.0/10minute'.
    """
    url = f"{HUAWEI_BASE_URL}/login"
    payload = {"username": username, "password": password}
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                token = res.headers.get("X-SRT") or res.headers.get("xsrt")
                return token, None
            elif data.get("failCode") in [407, 20002] or "frequency" in str(data.get("message")):
                return None, "⏳ **Limite login raggiunto (5 login in 10 min)**. Huawei ha temporaneamente bloccato i login. Attendi qualche minuto prima di riprovare."
            else:
                return None, f"Errore Login Huawei: {data.get('message')}"
        return None, f"Errore Server HTTP: {res.status_code}"
    except Exception as e:
        return None, f"Errore Connessione: {e}"

def fetch_huawei_data_with_token(token):
    """
    Recupera Stazioni e KPI usando il token già memorizzato.
    """
    headers = {"X-SRT": token, "Content-Type": "application/json"}
    
    try:
        # 1. Download Lista Stazioni
        list_url = f"{HUAWEI_BASE_URL}/getStationList"
        res_list = requests.post(list_url, json={}, headers=headers, timeout=12)
        data_list = res_list.json()
        
        if not data_list.get("success") or not data_list.get("data"):
            return None, f"Errore lista stazioni: {data_list.get('message')}"
        
        stations = data_list.get("data", [])
        
        # 2. Download KPI reali
        station_codes = [s.get("stationCode") for s in stations if s.get("stationCode")]
        kpi_map_result = {}
        
        if station_codes:
            kpi_url = f"{HUAWEI_BASE_URL}/getStationRealKpi"
            res_kpi = requests.post(kpi_url, json={"stationCodes": ",".join(station_codes)}, headers=headers, timeout=12)
            kpi_data = res_kpi.json()
            if kpi_data.get("success") and kpi_data.get("data"):
                for item in kpi_data.get("data", []):
                    kpi_map_result[item.get("stationCode")] = item.get("dataItemMap", {})
                    
        return {"stations": stations, "kpi_map": kpi_map_result}, None

    except Exception as e:
        return None, f"Errore download dati: {e}"

# ==========================================
# 4. CALCOLO PRODUZIONE ATTESA (OPEN-METEO)
# ==========================================
def get_expected_production_now(lat, lon, tilt, azimuth_user, kwp, pr=0.85):
    now_italy = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    current_hour = now_italy.hour
    current_minute = now_italy.minute

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
            hourly_tilted = data.get("hourly", {}).get("global_tilted_irradiance", [])

            if hourly_tilted:
                for h in range(min(current_hour, len(hourly_tilted))):
                    if hourly_tilted[h] is not None:
                        cumulative_poa_wh += float(hourly_tilted[h])

                if current_hour < len(hourly_tilted) and hourly_tilted[current_hour] is not None:
                    current_instant_w = float(hourly_tilted[current_hour])
                    cumulative_poa_wh += current_instant_w * (current_minute / 60.0)

    except Exception as e:
        st.warning(f"⚠️ Errore Open-Meteo ({lat}, {lon}): {e}")

    psh = cumulative_poa_wh / 1000.0
    expected_kwh = kwp * psh * pr

    return {
        "cumulative_poa_wh": round(cumulative_poa_wh, 2),
        "current_instant_w": round(current_instant_w, 2),
        "expected_kwh": round(expected_kwh, 2)
    }

# ==========================================
# 5. SIDEBAR CONFIGURAZIONE
# ==========================================
st.sidebar.header("⚙️ Impostazioni Globali")
performance_ratio = st.sidebar.slider("Performance Ratio (PR)", min_value=0.70, max_value=0.95, value=0.85, step=0.01)

st.sidebar.markdown("---")
st.sidebar.info(f"👤 Utente API dai Secrets: **{API_USER}**")

# ==========================================
# 6. DASHBOARD PRINCIPALE
# ==========================================
btn_fetch = st.button("🔄 Aggiorna Dati In Tempo Reale", type="primary")

if btn_fetch:
    if not API_PASS:
        st.error("Inserisci la password nei Secrets per procedere.")
    else:
        with st.spinner("Autenticazione in corso (Token con Cache)..."):
            token, err_login = get_huawei_token_cached(API_USER, API_PASS)

        if err_login:
            st.warning(err_login)
        else:
            with st.spinner("Recupero dati impianti da Huawei..."):
                huawei_data, err_data = fetch_huawei_data_with_token(token)

            if err_data:
                st.error(err_data)
            else:
                st.session_state["huawei_raw"] = huawei_data
                st.success("✅ Dati recuperati con successo da Huawei!")

# Se i dati sono in sessione, mostriamo la tabella
if "huawei_raw" in st.session_state:
    huawei_raw = st.session_state["huawei_raw"]
    stations = huawei_raw["stations"]
    kpi_map = huawei_raw["kpi_map"]

    now_str = datetime.datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y - %H:%M:%S")
    st.caption(f"🕒 Ultimo aggiornamento: **{now_str}** | Trovati **{len(stations)}** impianti reali.")

    if "plant_configs" not in st.session_state:
        st.session_state["plant_configs"] = {}

    config_rows = []
    for s in stations:
        code = s.get("stationCode")
        name = s.get("stationName")
        kwp = float(s.get("capacity", 0.0))
        
        cfg = st.session_state["plant_configs"].get(code, {"Tilt": 15, "Azimuth": 0})
        
        config_rows.append({
            "Codice": code,
            "Impianto": name,
            "kWp": kwp,
            "Tilt (°)": cfg["Tilt"],
            "Azimuth (°)": cfg["Azimuth"]
        })

    df_config_input = pd.DataFrame(config_rows)

    st.markdown("### 🛠️ Personalizza Inclinazione (Tilt) e Orientamento (Azimuth)")
    st.info("💡 Modifica i valori di **Tilt** e **Azimuth** per ciascun impianto direttamente nella tabella:")

    edited_df = st.data_editor(
        df_config_input,
        column_config={
            "Codice": st.column_config.TextColumn(disabled=True),
            "Impianto": st.column_config.TextColumn(disabled=True),
            "kWp": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "Tilt (°)": st.column_config.NumberColumn(min_value=0, max_value=90, step=1),
            "Azimuth (°)": st.column_config.NumberColumn(min_value=-180, max_value=180, step=1, help="0=SUD, -90=EST, 90=OVEST")
        },
        hide_index=True,
        use_container_width=True
    )

    for _, row in edited_df.iterrows():
        st.session_state["plant_configs"][row["Codice"]] = {
            "Tilt": int(row["Tilt (°)"]),
            "Azimuth": int(row["Azimuth (°)"])
        }

    results = []
    for s in stations:
        code = s.get("stationCode")
        name = s.get("stationName")
        kwp = float(s.get("capacity", 0.0))
        lat = float(s.get("latitude")) if s.get("latitude") else 46.06
        lon = float(s.get("longitude")) if s.get("longitude") else 13.23

        p_cfg = st.session_state["plant_configs"][code]
        tilt = p_cfg["Tilt"]
        azimuth = p_cfg["Azimuth"]

        plant_kpi = kpi_map.get(code, {})
        real_kwh = float(plant_kpi.get("day_power", 0.0))
        active_kw = float(plant_kpi.get("active_power", 0.0))

        meteo = get_expected_production_now(
            lat=lat,
            lon=lon,
            tilt=tilt,
            azimuth_user=azimuth,
            kwp=kwp,
            pr=performance_ratio
        )

        expected_kwh = meteo["expected_kwh"]
        perf_ratio = round((real_kwh / expected_kwh * 100), 1) if expected_kwh > 0 else 0.0

        results.append({
            "Impianto": name,
            "Potenza (kWp)": kwp,
            "Tilt / Azimuth": f"{tilt}° / {azimuth}°",
            "Potenza Istantanea (kW)": active_kw,
            "Produzione Reale (kWh)": real_kwh,
            "Produzione Attesa (kWh)": expected_kwh,
            "Performance (%)": perf_ratio,
            "Irraggiamento (W/m²)": meteo["current_instant_w"],
            "Irraggiamento Cum. (Wh/m²)": meteo["cumulative_poa_wh"]
        })

    df_res = pd.DataFrame(results)

    # --- KPI GLOBALI ---
    st.markdown("---")
    st.markdown("### 📊 Riepilogo Complessivo Risultati")
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
