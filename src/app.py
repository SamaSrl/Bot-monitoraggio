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
# 3. MANAGER SESSIONE PERSISTENTE HUAWEI
# ==========================================
HUAWEI_BASE_URL = "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1"

class HuaweiSessionManager:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.last_login_time = 0

    def login(self):
        """Effettua il login solo se necessario."""
        url = f"{HUAWEI_BASE_URL}/login"
        payload = {"username": self.username, "password": self.password}
        try:
            res = self.session.post(url, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    self.token = res.headers.get("X-SRT") or res.headers.get("xsrt")
                    self.session.headers.update({"X-SRT": self.token})
                    self.last_login_time = time.time()
                    return True, None
                msg = data.get("message", "Login fallito")
                if "frequency" in str(msg) or data.get("failCode") in [407, 20002]:
                    return False, "⏳ Rate limit login Huawei attivo. Attendi qualche minuto senza aggiornare la pagina."
                return False, f"Login fallito: {msg}"
            return False, f"Errore HTTP Login: {res.status_code}"
        except Exception as e:
            return False, f"Errore connessione Login: {e}"

    def ensure_valid_token(self):
        """Rigenera il token solo se sono trascorsi più di 20 minuti dall'ultimo login."""
        now = time.time()
        # Se non abbiamo un token o sono passati più di 20 minuti (1200 sec)
        if not self.token or (now - self.last_login_time) > 1200:
            return self.login()
        return True, None

    def get_data(self):
        # 1. Assicurati che il token sia valido
        ok, err = self.ensure_valid_token()
        if not ok:
            return None, err

        # 2. Recupera Lista Stazioni
        try:
            res_list = self.session.post(f"{HUAWEI_BASE_URL}/getStationList", json={}, timeout=12)
            data_list = res_list.json()

            # Se la sessione è invalida lato Huawei, ritenta il login UNA sola volta
            if not data_list.get("success") and ("USER_MUST_RELOGIN" in str(data_list.get("message")) or data_list.get("failCode") == 305):
                ok_relogin, err_relogin = self.login()
                if not ok_relogin:
                    return None, err_relogin
                res_list = self.session.post(f"{HUAWEI_BASE_URL}/getStationList", json={}, timeout=12)
                data_list = res_list.json()

            if not data_list.get("success"):
                return None, f"Errore Lista Stazioni: {data_list.get('message')}"

            stations = data_list.get("data", [])
            station_codes = [s.get("stationCode") for s in stations if s.get("stationCode")]

            # 3. Recupera Real KPI
            kpi_map = {}
            if station_codes:
                res_kpi = self.session.post(
                    f"{HUAWEI_BASE_URL}/getStationRealKpi",
                    json={"stationCodes": ",".join(station_codes)},
                    timeout=12
                )
                data_kpi = res_kpi.json()
                if data_kpi.get("success") and data_kpi.get("data"):
                    for item in data_kpi.get("data", []):
                        kpi_map[item.get("stationCode")] = item.get("dataItemMap", {})

            return {"stations": stations, "kpi_map": kpi_map}, None

        except Exception as e:
            return None, f"Errore recupero dati: {e}"

# Memorizza l'oggetto manager in memoria condivisa (evita login multipli tra i refresh di Streamlit)
@st.cache_resource
def get_huawei_manager(user, password):
    return HuaweiSessionManager(user, password)

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
btn_fetch = st.button("🔄 Aggiorna Dati In Tempo Reale", type="primary")

if btn_fetch or "huawei_raw" not in st.session_state:
    if API_PASS:
        with st.spinner("Lettura dati da Huawei FusionSolar..."):
            manager = get_huawei_manager(API_USER, API_PASS)
            huawei_data, err = manager.get_data()

        if err:
            st.error(f"⚠️ {err}")
        elif huawei_data:
            st.session_state["huawei_raw"] = huawei_data
            st.success("✅ Dati caricati con successo!")

# RENDERING DELLA DASHBOARD
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
