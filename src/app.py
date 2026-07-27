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
# 2. RECUPERO SECRETS
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
# 3. CHIAMATA ATOMICA ALL'API HUAWEI
# ==========================================
HUAWEI_BASE_URL = "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1"

@st.cache_data(ttl=900, show_spinner=False)
def fetch_huawei_data_cached(username, password):
    session = requests.Session()
    headers = {"Content-Type": "application/json"}

    # 1. LOGIN
    login_url = f"{HUAWEI_BASE_URL}/login"
    login_payload = {"username": username, "password": password}

    try:
        res_login = session.post(login_url, json=login_payload, headers=headers, timeout=12)
        
        if res_login.status_code != 200:
            return None, f"Errore HTTP Login: {res_login.status_code}"

        data_login = res_login.json()
        if not data_login.get("success"):
            msg = data_login.get("message", "")
            fail_code = data_login.get("failCode")
            if fail_code in [407, 20002] or "frequency" in str(msg).lower():
                return None, "⏳ Limitazione frequenza Huawei attiva (max 5 login in 10 min). Attendi 10 minuti prima di riprovare."
            return None, f"Login fallito: {msg} (failCode: {fail_code})"

        # Ricerca capillare del Token X-SRT negli header (case-insensitive) o nei cookies
        token = None
        for k, v in res_login.headers.items():
            if k.lower() == "x-srt":
                token = v
                break

        # Se non c'è negli header, cerchiamo tra i cookie di sessione
        if not token and "JSESSIONID" in session.cookies:
            token = session.cookies.get("JSESSIONID")

        if not token:
            # Mostra gli header ricevuti per debugging preciso
            return None, f"Token non trovato. Header ricevuti da Huawei: {dict(res_login.headers)}"

        # Assegna il token per le chiamate successive
        session.headers.update({
            "X-SRT": token, 
            "xsrt": token,
            "Content-Type": "application/json"
        })

        # 2. LISTA STAZIONI
        res_list = session.post(f"{HUAWEI_BASE_URL}/getStationList", json={}, timeout=12)
        data_list = res_list.json()

        if not data_list.get("success"):
            return None, f"Errore recupero stazioni: {data_list.get('message')} (failCode: {data_list.get('failCode')})"

        stations = data_list.get("data", [])
        if not stations:
            return None, "Nessun impianto associato a questo account API Huawei."

        # 3. REAL KPI STAZIONI
        station_codes = [s.get("stationCode") for s in stations if s.get("stationCode")]
        kpi_map = {}

        if station_codes:
            res_kpi = session.post(
                f"{HUAWEI_BASE_URL}/getStationRealKpi",
                json={"stationCodes": ",".join(station_codes[:100])},
                timeout=12
            )
            data_kpi = res_kpi.json()
            if data_kpi.get("success") and data_kpi.get("data"):
                for item in data_kpi.get("data", []):
                    kpi_map[item.get("stationCode")] = item.get("dataItemMap", {})

        return {"stations": stations, "kpi_map": kpi_map}, None

    except Exception as e:
        return None, f"Errore di rete/connessione: {e}"


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
        res = requests.get(url, timeout=8)
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

    except Exception:
        pass

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
st.sidebar.info(f"👤 Utente API: **{API_USER}**")

# ==========================================
# 6. DASHBOARD PRINCIPALE
# ==========================================
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    btn_fetch = st.button("🔄 Aggiorna Dati In Tempo Reale", type="primary")

if btn_fetch:
    st.cache_data.clear()

if API_PASS:
    with st.spinner("Connessione a Huawei FusionSolar in corso..."):
        huawei_data, err = fetch_huawei_data_cached(API_USER, API_PASS)

    if err:
        st.error(f"⚠️ {err}")
    elif huawei_data:
        st.session_state["huawei_raw"] = huawei_data

# RENDERING DASHBOARD
if "huawei_raw" in st.session_state and st.session_state["huawei_raw"]:
    huawei_raw = st.session_state["huawei_raw"]
    stations = huawei_raw["stations"]
    kpi_map = huawei_raw["kpi_map"]

    now_str = datetime.datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y - %H:%M:%S")
    st.caption(f"🕒 Ultimo aggiornamento: **{now_str}** | Impianti trovati: **{len(stations)}**")

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
