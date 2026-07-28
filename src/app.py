import streamlit as st
import requests
import time
import json
import os
import textwrap
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

st.set_page_config(page_title="FusionSolar Control Center", page_icon="🛰️", layout="wide")

def render_html(html):
    st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# CREDENZIALI & PERSISTENZA
# ----------------------------------------------------------------------------
API_USER = st.secrets.get("API_USER", "")
API_SYSTEM_CODE = st.secrets.get("API_SYSTEM_CODE", "")
BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"
TOKEN_VALIDITY_SECONDS = 25 * 60

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plant_config.json")

def load_plant_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_plant_config(config):
    tmp_path = CONFIG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, CONFIG_FILE)

# ----------------------------------------------------------------------------
# STILE DARK TEKNOLOGICO
# ----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, [class*="css"]  { font-family: 'Space Grotesk', sans-serif; }
    .stApp {
        background: radial-gradient(circle at 20% 0%, #0d1b2a 0%, #060a12 45%, #030407 100%);
        color: #e6edf3;
    }
    #MainMenu, footer, header { visibility: hidden; }

    .fs-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 18px 28px;
        margin-bottom: 24px;
        background: linear-gradient(135deg, rgba(0,229,255,0.08), rgba(0,120,255,0.03));
        border: 1px solid rgba(0,229,255,0.25);
        border-radius: 14px;
    }
    .fs-title { font-size: 26px; font-weight: 700; color: #ffffff; margin: 0; }
    .fs-subtitle { font-size: 13px; color: #7ee8fa; font-family: 'JetBrains Mono', monospace; margin-top: 4px; }
    
    .plant-card {
        background: linear-gradient(160deg, rgba(18,26,42,0.9), rgba(9,13,22,0.9));
        border: 1px solid rgba(255,255,255,0.07);
        border-left: 4px solid #00e5ff;
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .plant-name { font-size: 22px; font-weight: 700; color: #ffffff; }
    .plant-code { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #6fd8ff; background: rgba(0,229,255,0.08); padding: 4px 10px; border-radius: 6px; margin-left: 10px; }
    .plant-meta { font-size: 14px; color: #9fb0c3; margin-top: 12px; font-family: 'JetBrains Mono', monospace; }
    .plant-meta span { margin-right: 24px; }

    .metric-box {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-title { font-size: 12px; text-transform: uppercase; color: #8ea3b8; font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; }
    .metric-num { font-size: 32px; font-weight: 700; color: #ffffff; margin-top: 6px; }

    .deviation-chip-ok { display: inline-block; padding: 6px 16px; border-radius: 999px; background: rgba(0,255,136,0.12); border: 1px solid rgba(0,255,136,0.5); color: #00ff88; font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 600; }
    .deviation-chip-bad { display: inline-block; padding: 6px 16px; border-radius: 999px; background: rgba(255,59,59,0.12); border: 1px solid rgba(255,59,59,0.5); color: #ff8080; font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# LOGICA API HUAWEI
# ----------------------------------------------------------------------------
if "fs_session" not in st.session_state: st.session_state.fs_session = None
if "token_time" not in st.session_state: st.session_state.token_time = 0
if "stations" not in st.session_state: st.session_state.stations = None
if "plant_config" not in st.session_state: st.session_state.plant_config = load_plant_config()

def do_login():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    res = session.post(f"{BASE_DOMAIN}/thirdData/login", json={"userName": API_USER, "systemCode": API_SYSTEM_CODE}, timeout=12)
    data = res.json()
    if not data.get("success"): raise RuntimeError(f"Login fallito")
    token = res.headers.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")
    session.headers.update({"xsrf-token": token})
    return session

def get_authenticated_session():
    now = time.time()
    if st.session_state.fs_session and (now - st.session_state.token_time) < TOKEN_VALIDITY_SECONDS:
        return st.session_state.fs_session
    session = do_login()
    st.session_state.fs_session = session
    st.session_state.token_time = now
    return session

def fetch_stations():
    session = get_authenticated_session()
    res = session.post(f"{BASE_DOMAIN}/thirdData/getStationList", json={}, timeout=15)
    data = res.json()
    st.session_state.stations = data.get("data") or []
    return st.session_state.stations

def fetch_yesterday_real_kwh(station_code):
    """Recupera la produzione reale accumulata (kWh) dalle chiamate orari Huawei per IERI."""
    session = get_authenticated_session()
    rome = ZoneInfo("Europe/Rome")
    yesterday_date = (datetime.now(rome) - timedelta(days=1)).date()
    y_midnight = datetime(yesterday_date.year, yesterday_date.month, yesterday_date.day, 0, 0, 0, tzinfo=rome)
    y_end = y_midnight + timedelta(days=1)
    
    res = session.post(f"{BASE_DOMAIN}/thirdData/getKpiStationHour", json={"stationCodes": station_code, "collectTime": int(y_midnight.timestamp() * 1000)}, timeout=15)
    data = res.json()
    
    total = 0.0
    for rec in data.get("data") or []:
        rec_time = rec.get("collectTime", 0)
        if int(y_midnight.timestamp() * 1000) <= rec_time < int(y_end.timestamp() * 1000):
            item = rec.get("dataItemMap", {}) or {}
            val = item.get("inverter_power") or item.get("product_power") or 0
            total += float(val)
    return round(total, 2), yesterday_date.strftime("%d/%m/%Y")

# ----------------------------------------------------------------------------
# CALCOLO METEO ATTESO PER IERI
# ----------------------------------------------------------------------------
def get_expected_production_yesterday(lat, lon, tilt, azimuth, capacity_kwp, pr=0.80):
    """
    Richiede a Open-Meteo l'irraggiamento sul piano inclinato (GTI) per l'intera giornata di IERI.
    Formula: kWp * sum(GTI_orario / 1000) * PR
    """
    rome = ZoneInfo("Europe/Rome")
    yesterday_date = (datetime.now(rome) - timedelta(days=1)).date().isoformat()

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "global_tilted_irradiance",
        "tilt": tilt,
        "azimuth": azimuth,
        "start_date": yesterday_date,
        "end_date": yesterday_date,
        "timezone": "Europe/Rome"
    }
    
    res = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=12)
    res.raise_for_status()
    data = res.json()
    
    gti_list = data.get("hourly", {}).get("global_tilted_irradiance", [])
    
    # Somma di tutti i punti orari delle 24h di ieri
    total_gti_wh = sum(g for g in gti_list if g is not None)
    peak_sun_hours = total_gti_wh / 1000.0  # Ore di sole equivalente
    
    expected_kwh = capacity_kwp * peak_sun_hours * pr
    
    return round(expected_kwh, 2), round(peak_sun_hours, 2), gti_list

# ----------------------------------------------------------------------------
# HEADER PRINCIPALE
# ----------------------------------------------------------------------------
st.markdown("""
<div class="fs-header">
    <div>
        <p class="fs-title">🛰️ FusionSolar Control Center</p>
        <p class="fs-subtitle">CONFRONTO PRODUZIONE REALE VS METEO ATTESA (GIORNO PRECEDENTE)</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Caricamento impianti
if not st.session_state.stations:
    with st.spinner("Connessione a Huawei e caricamento impianti..."):
        fetch_stations()

stations = st.session_state.stations or []

# Isoliamo l'impianto di Rivignano
rivignano_station = next((s for s in stations if "rivignano" in str(s.get("stationName", "")).lower()), None)
if not rivignano_station and stations:
    rivignano_station = stations[0]

# ----------------------------------------------------------------------------
# SIDEBAR LATERALE (SOLO INPUT E PARAMETRI)
# ----------------------------------------------------------------------------
st.sidebar.header("⚙️ Parametri Impianto")

if rivignano_station:
    code = rivignano_station.get("stationCode")
    name = rivignano_station.get("stationName")
    
    st.sidebar.subheader(f"📍 {name}")
    st.sidebar.caption(f"Codice: `{code}`")
    
    saved_cfg = st.session_state.plant_config.get(code, {})
    
    tilt_val = st.sidebar.number_input("Tilt / Inclinazione (°)", min_value=0.0, max_value=90.0, value=float(saved_cfg.get("tilt", 30.0)), step=1.0)
    azimuth_val = st.sidebar.number_input("Azimut (°)", min_value=-180.0, max_value=180.0, value=float(saved_cfg.get("azimuth", 0.0)), step=1.0, help="0=Sud, -90=Est, +90=Ovest")
    
    def_lat = saved_cfg.get("lat") or rivignano_station.get("latitude") or 45.875
    def_lon = saved_cfg.get("lon") or rivignano_station.get("longitude") or 13.042
    
    lat_val = st.sidebar.number_input("Latitudine", value=float(def_lat), format="%.6f")
    lon_val = st.sidebar.number_input("Longitudine", value=float(def_lon), format="%.6f")
    
    pr_val = st.sidebar.slider("Performance Ratio (PR)", min_value=0.50, max_value=1.00, value=float(saved_cfg.get("pr", 0.80)), step=0.01, help="Coefficiente di perdite dell'impianto (tipicamente tra 0.75 e 0.85)")

    if st.sidebar.button("💾 Salva e Ricalcola", type="primary", use_container_width=True):
        st.session_state.plant_config[code] = {
            "tilt": tilt_val, "azimuth": azimuth_val,
            "lat": lat_val, "lon": lon_val, "pr": pr_val
        }
        save_plant_config(st.session_state.plant_config)
        st.sidebar.success("Parametri salvati!")

# ----------------------------------------------------------------------------
# PAGINA PRINCIPALE (VISUALIZZAZIONE E CONFRONTO IERI)
# ----------------------------------------------------------------------------
if rivignano_station:
    code = rivignano_station.get("stationCode")
    name = rivignano_station.get("stationName")
    addr = rivignano_station.get("stationAddr", "Rivignano")
    capacity = float(rivignano_station.get("capacity") or 0.0)
    
    # 1. Dati Reali Huawei Ieri
    yesterday_real_kwh, date_str = fetch_yesterday_real_kwh(code)
    
    # 2. Dati Meteo Attesi Ieri
    yesterday_exp_kwh, psh, gti_hourly = get_expected_production_yesterday(lat_val, lon_val, tilt_val, azimuth_val, capacity, pr_val)

    # 3. Scostamento
    deviation = ((yesterday_real_kwh - yesterday_exp_kwh) / yesterday_exp_kwh * 100) if yesterday_exp_kwh > 0 else 0
    dev_class = "deviation-chip-ok" if deviation >= -8 else "deviation-chip-bad"
    sign = "+" if deviation >= 0 else ""

    # Card Info Impianto
    st.markdown(f"""
    <div class="plant-card">
        <span class="plant-name">☀️ {name}</span><span class="plant-code">{code}</span>
        <div class="plant-meta">
            <span>📍 Location: <b>{addr}</b></span>
            <span>⚡ Potenza Nominale: <b>{capacity} kWp</b></span>
            <span>📐 Configurazione: <b>Tilt {tilt_val}° | Azimut {azimuth_val}°</b></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader(f"📊 Analisi Resa di Ieri ({date_str})")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Produzione Reale (Huawei)</div>
            <div class="metric-num" style="color: #00e5ff;">{yesterday_real_kwh:,.1f} <span style="font-size:16px;">kWh</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Produzione Attesa (Meteo)</div>
            <div class="metric-num" style="color: #ffcf5c;">{yesterday_exp_kwh:,.1f} <span style="font-size:16px;">kWh</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Scostamento Prestazione</div>
            <div style="margin-top:12px;"><span class="{dev_class}">{sign}{deviation:.1f}%</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Tabella Dettaglio Tecnico
    with st.expander("🔍 Dettaglio dei Calcoli e Irraggiamento Meteo di Ieri"):
        st.write(f"* **Ore Equivalenti di Sole (Peak Sun Hours):** `{psh} h`")
        st.write(f"* **Formula applicata:** `{capacity} kWp × {psh} h × {pr_val} (PR) = {yesterday_exp_kwh} kWh`")
        
        df_debug = pd.DataFrame({
            "Ora": [f"{h:02d}:00" for h in range(24)],
            "Irraggiamento GTI (W/m²)": gti_hourly
        })
        st.dataframe(df_debug.T, use_container_width=True)

else:
    st.warning("Impianto non trovato o errore durante l'autenticazione.")
