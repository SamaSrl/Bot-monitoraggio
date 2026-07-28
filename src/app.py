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
# STILE DARK CYBERPUNK
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
        padding: 20px;
        margin-bottom: 20px;
    }
    .plant-name { font-size: 20px; font-weight: 700; color: #ffffff; }
    .plant-code { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #6fd8ff; background: rgba(0,229,255,0.08); padding: 3px 8px; border-radius: 6px; margin-left: 8px; }
    .plant-meta { font-size: 13px; color: #9fb0c3; margin-top: 10px; font-family: 'JetBrains Mono', monospace; }
    .plant-meta span { margin-right: 20px; }

    .metric-box {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    .metric-title { font-size: 11px; text-transform: uppercase; color: #8ea3b8; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.5px; }
    .metric-num { font-size: 24px; font-weight: 700; color: #ffffff; margin-top: 4px; }

    .deviation-chip-ok { display: inline-block; padding: 4px 12px; border-radius: 999px; background: rgba(0,255,136,0.12); border: 1px solid rgba(0,255,136,0.5); color: #00ff88; font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; }
    .deviation-chip-bad { display: inline-block; padding: 4px 12px; border-radius: 999px; background: rgba(255,59,59,0.12); border: 1px solid rgba(255,59,59,0.5); color: #ff8080; font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# API HUAWEI
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
# CALCOLO METEO ATTESO
# ----------------------------------------------------------------------------
def get_expected_production_yesterday(lat, lon, tilt, azimuth, capacity_kwp, pr=0.80):
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
    
    try:
        res = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=12)
        res.raise_for_status()
        data = res.json()
        gti_list = data.get("hourly", {}).get("global_tilted_irradiance", [])
        
        total_gti_wh = sum(g for g in gti_list if g is not None)
        peak_sun_hours = total_gti_wh / 1000.0
        expected_kwh = capacity_kwp * peak_sun_hours * pr
        
        return round(expected_kwh, 2), round(peak_sun_hours, 2), gti_list
    except Exception:
        return 0.0, 0.0, []

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown("""
<div class="fs-header">
    <div>
        <p class="fs-title">🛰️ FusionSolar Control Center</p>
        <p class="fs-subtitle">MONITORAGGIO MULTI-IMPIANTO · ANALISI PRESTAZIONE GIORNO PRECEDENTE</p>
    </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.stations:
    with st.spinner("Caricamento impianti in corso..."):
        fetch_stations()

stations = st.session_state.stations or []

# ----------------------------------------------------------------------------
# SIDEBAR LATERALE (GESTIONE CONFIGURAZIONE IMPIANTI)
# ----------------------------------------------------------------------------
st.sidebar.header("⚙️ Configurazione Impianto")

if stations:
    station_names = [s.get("stationName", "Senza Nome") for s in stations]
    selected_name = st.sidebar.selectbox("Seleziona Impianto da Configurare", station_names)
    
    selected_st = next(s for s in stations if s.get("stationName") == selected_name)
    code = selected_st.get("stationCode")
    
    st.sidebar.markdown("---")
    saved_cfg = st.session_state.plant_config.get(code, {})
    
    # Auto-fix capacità (se Huawei invia 1.131 assumiamo intenda 1131 kWp)
    raw_capacity = float(selected_st.get("capacity") or 0.0)
    if 0 < raw_capacity < 10 and "rivignano" in selected_name.lower():
        raw_capacity = raw_capacity * 1000.0

    cap_val = st.sidebar.number_input("Potenza Nominale (kWp)", min_value=0.0, value=float(saved_cfg.get("capacity", raw_capacity)), step=10.0)
    tilt_val = st.sidebar.number_input("Tilt / Inclinazione (°)", min_value=0.0, max_value=90.0, value=float(saved_cfg.get("tilt", 30.0)), step=1.0)
    azimuth_val = st.sidebar.number_input("Azimut (°)", min_value=-180.0, max_value=180.0, value=float(saved_cfg.get("azimuth", 0.0)), step=1.0, help="0=Sud, -90=Est, +90=Ovest")
    
    def_lat = saved_cfg.get("lat") or selected_st.get("latitude") or 45.875
    def_lon = saved_cfg.get("lon") or selected_st.get("longitude") or 13.042
    
    lat_val = st.sidebar.number_input("Latitudine", value=float(def_lat), format="%.6f")
    lon_val = st.sidebar.number_input("Longitudine", value=float(def_lon), format="%.6f")
    
    pr_val = st.sidebar.slider("Performance Ratio (PR)", min_value=0.50, max_value=1.00, value=float(saved_cfg.get("pr", 0.80)), step=0.01)

    if st.sidebar.button("💾 Salva Configurazione", type="primary", use_container_width=True):
        st.session_state.plant_config[code] = {
            "capacity": cap_val, "tilt": tilt_val, "azimuth": azimuth_val,
            "lat": lat_val, "lon": lon_val, "pr": pr_val
        }
        save_plant_config(st.session_state.plant_config)
        st.sidebar.success("Configurazione salvata con successo!")

# ----------------------------------------------------------------------------
# PAGINA PRINCIPALE (LISTA DI TUTTI GLI IMPIANTI)
# ----------------------------------------------------------------------------
if not stations:
    st.warning("Nessun impianto trovato o errore durante il login.")
else:
    for st_item in stations:
        st_code = st_item.get("stationCode")
        st_name = st_item.get("stationName")
        st_addr = st_item.get("stationAddr", "N/D")
        
        # Recupera parametri salvati o default
        cfg = st.session_state.plant_config.get(st_code, {})
        
        raw_cap = float(st_item.get("capacity") or 0.0)
        if 0 < raw_cap < 10 and "rivignano" in st_name.lower():
            raw_cap = raw_cap * 1000.0
            
        capacity = float(cfg.get("capacity", raw_cap))
        tilt = float(cfg.get("tilt", 30.0))
        azimuth = float(cfg.get("azimuth", 0.0))
        lat = float(cfg.get("lat") or st_item.get("latitude") or 45.875)
        lon = float(cfg.get("lon") or st_item.get("longitude") or 13.042)
        pr = float(cfg.get("pr", 0.80))

        # Calcoli Ieri
        real_kwh, date_str = fetch_yesterday_real_kwh(st_code)
        exp_kwh, psh, _ = get_expected_production_yesterday(lat, lon, tilt, azimuth, capacity, pr)
        
        dev = ((real_kwh - exp_kwh) / exp_kwh * 100) if exp_kwh > 0 else 0
        dev_class = "deviation-chip-ok" if dev >= -8 else "deviation-chip-bad"
        sign = "+" if dev >= 0 else ""

        # Card Impianto
        st.markdown(f"""
        <div class="plant-card">
            <span class="plant-name">☀️ {st_name}</span><span class="plant-code">{st_code}</span>
            <div class="plant-meta">
                <span>📍 Location: <b>{st_addr}</b></span>
                <span>⚡ Potenza: <b>{capacity:,.1f} kWp</b></span>
                <span>📐 Tilt: <b>{tilt}°</b> | Azimut: <b>{azimuth}°</b> | PR: <b>{pr}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-title">Produzione Reale ({date_str})</div>
                <div class="metric-num" style="color: #00e5ff;">{real_kwh:,.1f} <span style="font-size:14px;">kWh</span></div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-title">Produzione Attesa (Meteo)</div>
                <div class="metric-num" style="color: #ffcf5c;">{exp_kwh:,.1f} <span style="font-size:14px;">kWh</span></div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-title">Scostamento Prestazione</div>
                <div style="margin-top:6px;"><span class="{dev_class}">{sign}{dev:.1f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
