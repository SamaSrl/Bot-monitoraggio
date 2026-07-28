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
    """st.markdown con unsafe_allow_html, ma prima rimuove l'indentazione
    Python della stringa: senza questo, le righe rientrate vengono a volte
    interpretate come blocchi di codice Markdown invece che come HTML."""
    st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# CREDENZIALI — non hardcodare.
# ----------------------------------------------------------------------------
API_USER = st.secrets.get("API_USER", "")
API_SYSTEM_CODE = st.secrets.get("API_SYSTEM_CODE", "")
BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"
TOKEN_VALIDITY_SECONDS = 25 * 60  # rinnova login prima della scadenza reale (~30 min)

# ----------------------------------------------------------------------------
# CONFIGURAZIONE PERSISTENTE PER IMPIANTO
# ----------------------------------------------------------------------------
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
# STYLE — tema dark "tecnologico"
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
        box-shadow: 0 0 30px rgba(0,229,255,0.08);
    }
    .fs-title {
        font-size: 26px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #ffffff;
        margin: 0;
    }
    .fs-subtitle {
        font-size: 13px;
        color: #7ee8fa;
        font-family: 'JetBrains Mono', monospace;
        margin-top: 4px;
        letter-spacing: 0.5px;
    }
    .fs-badge-online {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        background: rgba(0,255,136,0.08);
        border: 1px solid rgba(0,255,136,0.4);
        color: #00ff88;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 500;
    }
    .fs-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: #00ff88;
        box-shadow: 0 0 8px #00ff88;
        animation: pulse 1.6s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; } 50% { opacity: 0.35; } 100% { opacity: 1; }
    }

    .metric-card {
        background: linear-gradient(145deg, rgba(20,30,48,0.8), rgba(10,16,28,0.8));
        border: 1px solid rgba(0,229,255,0.18);
        border-radius: 14px;
        padding: 18px 22px;
        text-align: left;
        transition: all 0.2s ease;
    }
    .metric-card:hover {
        border-color: rgba(0,229,255,0.5);
        box-shadow: 0 0 22px rgba(0,229,255,0.12);
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #8ea3b8;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-value {
        font-size: 30px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 4px;
    }
    .metric-accent { color: #00e5ff; }

    .plant-card {
        background: linear-gradient(160deg, rgba(18,26,42,0.9), rgba(9,13,22,0.9));
        border: 1px solid rgba(255,255,255,0.07);
        border-left: 3px solid #00e5ff;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 12px;
        transition: all 0.15s ease;
    }
    .plant-card:hover {
        border-left-color: #00ff88;
        background: linear-gradient(160deg, rgba(22,32,50,0.95), rgba(11,16,26,0.95));
    }
    .plant-name {
        font-size: 16px;
        font-weight: 600;
        color: #ffffff;
    }
    .plant-code {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #6fd8ff;
        background: rgba(0,229,255,0.08);
        padding: 2px 8px;
        border-radius: 6px;
        margin-left: 8px;
    }
    .plant-meta {
        font-size: 13px;
        color: #9fb0c3;
        margin-top: 6px;
        font-family: 'JetBrains Mono', monospace;
    }
    .plant-meta span { margin-right: 18px; }

    .led {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 10px;
        vertical-align: middle;
        position: relative;
        top: -1px;
    }
    .led-green {
        background: #00ff88;
        box-shadow: 0 0 6px #00ff88, 0 0 14px rgba(0,255,136,0.6);
    }
    .led-red {
        background: #ff3b3b;
        box-shadow: 0 0 6px #ff3b3b, 0 0 14px rgba(255,59,59,0.7);
        animation: pulse-red 1.2s infinite;
    }
    .led-gray {
        background: #6b7688;
        box-shadow: 0 0 4px rgba(107,118,136,0.5);
    }
    @keyframes pulse-red {
        0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; }
    }
    .plant-card-alarm {
        border-left: 3px solid #ff3b3b !important;
        background: linear-gradient(160deg, rgba(50,15,15,0.5), rgba(9,13,22,0.9)) !important;
    }
    .alarm-box {
        margin-top: 8px;
        padding: 8px 12px;
        background: rgba(255,59,59,0.08);
        border: 1px solid rgba(255,59,59,0.35);
        border-radius: 8px;
        font-size: 12.5px;
        color: #ffb3b3;
        font-family: 'JetBrains Mono', monospace;
    }
    .production-chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: rgba(255,183,0,0.1);
        border: 1px solid rgba(255,183,0,0.4);
        color: #ffcf5c;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        margin-right: 8px;
    }
    .deviation-chip-ok {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: rgba(0,255,136,0.1);
        border: 1px solid rgba(0,255,136,0.4);
        color: #00ff88;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }
    .deviation-chip-warn {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: rgba(255,183,0,0.12);
        border: 1px solid rgba(255,183,0,0.45);
        color: #ffcf5c;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }
    .deviation-chip-bad {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: rgba(255,59,59,0.1);
        border: 1px solid rgba(255,59,59,0.45);
        color: #ff8080;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }

    div[data-testid="stTextInput"] input {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(0,229,255,0.25);
        color: #e6edf3;
        border-radius: 10px;
    }

    .stButton > button {
        background: linear-gradient(135deg, #0091ff, #00d4ff);
        color: #061018;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        padding: 10px 22px;
        letter-spacing: 0.3px;
        box-shadow: 0 0 20px rgba(0,212,255,0.25);
    }
    .stButton > button:hover {
        box-shadow: 0 0 28px rgba(0,212,255,0.45);
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown("""
<div class="fs-header">
    <div>
        <p class="fs-title">🛰️ FusionSolar Control Center</p>
        <p class="fs-subtitle">NORTHBOUND API GATEWAY · EU5 REGION</p>
    </div>
    <div class="fs-badge-online"><span class="fs-dot"></span> API CONNECTED</div>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# SESSION STATE INIT
# ----------------------------------------------------------------------------
if "fs_session" not in st.session_state:
    st.session_state.fs_session = None
if "token_time" not in st.session_state:
    st.session_state.token_time = 0
if "stations" not in st.session_state:
    st.session_state.stations = None
if "enriched_at" not in st.session_state:
    st.session_state.enriched_at = None
if "plant_config" not in st.session_state:
    st.session_state.plant_config = load_plant_config()
if "expected_results" not in st.session_state:
    st.session_state.expected_results = {}


def do_login():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    res = session.post(
        f"{BASE_DOMAIN}/thirdData/login",
        json={"userName": API_USER, "systemCode": API_SYSTEM_CODE},
        timeout=12,
    )
    data = res.json()
    if not data.get("success"):
        raise RuntimeError(data.get("message") or f"Login fallito (failCode {data.get('failCode')})")

    headers_lower = {k.lower(): v for k, v in res.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")
    if not token:
        raise RuntimeError("Token non trovato nella risposta di login")

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


def fetch_stations(force=False):
    if not API_USER or not API_SYSTEM_CODE:
        st.error("Imposta API_USER e API_SYSTEM_CODE in .streamlit/secrets.toml")
        st.stop()

    if force:
        st.session_state.fs_session = None
        st.session_state.stations = None

    session = get_authenticated_session()
    res = session.post(f"{BASE_DOMAIN}/thirdData/getStationList", json={}, timeout=15)
    data = res.json()

    if not data.get("success"):
        if data.get("failCode") in (407, 305) and not force:
            return fetch_stations(force=True)
        raise RuntimeError(data.get("message") or f"failCode {data.get('failCode')}")

    st.session_state.stations = data.get("data") or []
    return st.session_state.stations


def _chunk(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _post_kpi(session, endpoint, codes, extra_body=None, batch_size=100):
    results = []
    for batch in _chunk(codes, batch_size):
        body = {"stationCodes": ",".join(batch)}
        if extra_body:
            body.update(extra_body)
        res = session.post(f"{BASE_DOMAIN}{endpoint}", json=body, timeout=15)
        data = res.json()
        if not data.get("success"):
            raise RuntimeError(
                f"{endpoint} fallito: {data.get('message') or ('failCode ' + str(data.get('failCode')))}"
            )
        results.extend(data.get("data") or [])
    return results


HEALTH_OK = "3"
HEALTH_ALARM = "2"
HEALTH_DISCONNECTED = "1"


def fetch_health_and_yesterday_production(stations):
    session = get_authenticated_session()
    codes = [s.get("stationCode") for s in stations if s.get("stationCode")]
    if not codes:
        return stations

    health_by_code = {}
    try:
        kpi_data = _post_kpi(session, "/thirdData/getStationRealKpi", codes)
        for rec in kpi_data:
            code = rec.get("stationCode")
            item = rec.get("dataItemMap", {}) or {}
            health_by_code[code] = item.get("real_health_state")
    except Exception as e:
        st.warning(f"⚠️ Impossibile recuperare lo stato di salute impianti: {e}")

    alarm_codes = [c for c, h in health_by_code.items() if h and str(h) != HEALTH_OK]
    alarms_by_code = {}
    if alarm_codes:
        try:
            now_ms = int(time.time() * 1000)
            week_ago_ms = now_ms - 7 * 24 * 60 * 60 * 1000
            alarm_data = _post_kpi(
                session, "/thirdData/getAlarmList", alarm_codes,
                extra_body={"beginTime": week_ago_ms, "endTime": now_ms},
                batch_size=100,
            )
            for a in alarm_data:
                code = a.get("stationCode") or a.get("nStationCode")
                name = a.get("alarmName") or a.get("faultName") or "Allarme sconosciuto"
                alarms_by_code.setdefault(code, []).append(name)
        except Exception as e:
            st.warning(f"⚠️ Impossibile recuperare il dettaglio allarmi: {e}")

    prod_by_code = {}
    raw_kpi_by_code = {}
    try:
        rome = ZoneInfo("Europe/Rome")
        now_rome = datetime.now(rome)
        yesterday_date = (now_rome - timedelta(days=1)).date()
        y_midnight = datetime(yesterday_date.year, yesterday_date.month, yesterday_date.day,
                               0, 0, 0, tzinfo=rome)
        y_end = y_midnight + timedelta(days=1)
        collect_time_ms = int(y_midnight.timestamp() * 1000)

        hourly_data = _post_kpi(
            session, "/thirdData/getKpiStationHour", codes,
            extra_body={"collectTime": collect_time_ms},
        )

        sums = {}
        hourly_debug = {}
        for rec in hourly_data:
            code = rec.get("stationCode")
            item = rec.get("dataItemMap", {}) or {}
            rec_time_ms = rec.get("collectTime")

            in_range = (
                rec_time_ms is not None
                and int(y_midnight.timestamp() * 1000) <= rec_time_ms < int(y_end.timestamp() * 1000)
            )
            if not in_range:
                continue

            val = item.get("inverter_power") or item.get("product_power") or item.get("power_profit")
            if val is not None:
                sums[code] = sums.get(code, 0) + float(val)
            hourly_debug.setdefault(code, []).append({"collectTime": rec_time_ms, "dataItemMap": item})

        for code, total in sums.items():
            prod_by_code[code] = round(total, 2)
        raw_kpi_by_code = hourly_debug
    except Exception as e:
        st.warning(f"⚠️ Impossibile recuperare la produzione di ieri: {e}")

    for s in stations:
        code = s.get("stationCode")
        s["health_state"] = health_by_code.get(code)
        s["alarm_texts"] = alarms_by_code.get(code, [])
        s["yesterday_kwh"] = prod_by_code.get(code)
        s["_raw_kpi"] = raw_kpi_by_code.get(code)

    return stations


def get_expected_production_yesterday(lat, lon, tilt, azimuth, capacity_kwp, performance_ratio=0.80):
    """Calcola la produzione attesa di ieri usando Open-Meteo."""
    rome = ZoneInfo("Europe/Rome")
    yesterday = (datetime.now(rome) - timedelta(days=1)).date().isoformat()

    # Utilizzo past_days=2 nell'API forecast per garantire di avere l'intero giorno di ieri
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "global_tilted_irradiance",
        "tilt": tilt,
        "azimuth": azimuth,
        "start_date": yesterday,
        "end_date": yesterday,
        "timezone": "Europe/Rome",
    }
    res = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
    res.raise_for_status()
    data = res.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    gti_values = hourly.get("global_tilted_irradiance", [])

    if not capacity_kwp or capacity_kwp <= 0:
        raise ValueError("Potenza installata (kWp) mancante o non valida per questo impianto")

    total_kwh = 0.0
    for gti in gti_values:
        if gti is None:
            continue
        total_kwh += (gti / 1000.0) * capacity_kwp * performance_ratio

    debug = {
        "date": yesterday,
        "n_hourly_points": len(times),
        "hourly_time": times,
        "hourly_gti_w_m2": gti_values,
    }
    return round(total_kwh, 2), debug


def get_yesterday_date_str():
    rome = ZoneInfo("Europe/Rome")
    return (datetime.now(rome) - timedelta(days=1)).date().isoformat()


def calculate_expected_for_configured(stations, force=False):
    target_date = get_yesterday_date_str()
    by_code = {s.get("stationCode"): s for s in stations}

    for code, cfg in st.session_state.plant_config.items():
        cached = st.session_state.expected_results.get(code)
        if cached and cached.get("date") == target_date and not force:
            continue
        station = by_code.get(code)
        if not station:
            continue
        try:
            cap = station.get("capacity")
            cap = float(cap) if cap not in (None, "N/D", "") else None
            expected_kwh, raw_debug = get_expected_production_yesterday(
                cfg.get("lat"), cfg.get("lon"), cfg.get("tilt"), cfg.get("azimuth"),
                cap, cfg.get("pr", 0.80),
            )
            st.session_state.expected_results[code] = {
                "expected_kwh": expected_kwh, "raw_debug": raw_debug, "date": target_date,
            }
        except Exception as e:
            st.session_state.expected_results[code] = {"error": str(e), "date": target_date}


# ----------------------------------------------------------------------------
# CARICAMENTO AUTOMATICO
# ----------------------------------------------------------------------------
if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = False

col_a, col_b = st.columns([1, 5])
with col_a:
    refresh_clicked = st.button("🔄 Aggiorna tutto")

if not st.session_state.auto_loaded or refresh_clicked:
    with st.spinner("Connessione al gateway FusionSolar e caricamento impianti..."):
        try:
            fetch_stations(force=refresh_clicked)
        except Exception as e:
            st.error(f"❌ Errore nel caricamento impianti: {e}")

    if st.session_state.stations:
        with st.spinner("Recupero stato, allarmi e produzione di ieri..."):
            try:
                st.session_state.stations = fetch_health_and_yesterday_production(st.session_state.stations)
                st.session_state.enriched_at = time.time()
            except Exception as e:
                st.error(f"❌ Errore nel recupero stato/produzione: {e}")

        if st.session_state.plant_config:
            with st.spinner("Calcolo produzione attesa per gli impianti configurati..."):
                calculate_expected_for_configured(st.session_state.stations, force=refresh_clicked)

    st.session_state.auto_loaded = True


# ----------------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Configurazione impianti")

    stations_for_sidebar = st.session_state.stations or []

    if not stations_for_sidebar:
        st.info("Carica prima gli impianti dalla pagina principale.")
    else:
        options = {
            f"{s.get('stationName', 'N/D')}  ·  {s.get('stationCode', '')}": s.get("stationCode")
            for s in stations_for_sidebar
        }
        label_list = list(options.keys())
        choice_label = st.selectbox("Seleziona impianto", label_list, key="sidebar_plant_choice")
        sel_code = options[choice_label]
        sel_station = next((s for s in stations_for_sidebar if s.get("stationCode") == sel_code), {})

        saved_cfg = st.session_state.plant_config.get(sel_code, {})
        default_lat = saved_cfg.get("lat") or sel_station.get("latitude") or sel_station.get("stationLatitude") or 0.0
        default_lon = saved_cfg.get("lon") or sel_station.get("longitude") or sel_station.get("stationLongitude") or 0.0

        tilt_val = st.number_input(
            "Tilt (°)", min_value=0.0, max_value=90.0,
            value=float(saved_cfg.get("tilt", 30.0)), step=1.0, key=f"sb_tilt_{sel_code}",
            help="Inclinazione dei pannelli rispetto all'orizzontale"
        )
        azimuth_val = st.number_input(
            "Azimut (°)", min_value=-180.0, max_value=180.0,
            value=float(saved_cfg.get("azimuth", 0.0)), step=1.0, key=f"sb_az_{sel_code}",
            help="0 = Sud, -90 = Est, +90 = Ovest, ±180 = Nord"
        )
        lat_val = st.number_input(
            "Latitudine", value=float(default_lat), format="%.6f", key=f"sb_lat_{sel_code}"
        )
        lon_val = st.number_input(
            "Longitudine", value=float(default_lon), format="%.6f", key=f"sb_lon_{sel_code}"
        )
        pr_val = st.slider(
            "Performance Ratio", min_value=0.50, max_value=1.00,
            value=float(saved_cfg.get("pr", 0.80)), step=0.01, key=f"sb_pr_{sel_code}",
            help="Perdite di sistema: inverter, cablaggio, temperatura, sporcizia. Tipico: 0.75–0.85"
        )

        if st.button("💾 Salva e calcola scostamento", type="primary", use_container_width=True):
            st.session_state.plant_config[sel_code] = {
                "tilt": tilt_val, "azimuth": azimuth_val,
                "lat": lat_val, "lon": lon_val, "pr": pr_val,
            }
            save_plant_config(st.session_state.plant_config)
            try:
                cap = sel_station.get("capacity")
                cap = float(cap) if cap not in (None, "N/D", "") else None
                expected_kwh, raw_debug = get_expected_production_yesterday(
                    lat_val, lon_val, tilt_val, azimuth_val, cap, pr_val
                )
                st.session_state.expected_results[sel_code] = {
                    "expected_kwh": expected_kwh, "raw_debug": raw_debug,
                    "date": get_yesterday_date_str(),
                }
                st.success(f"✅ Salvato. Produzione attesa ieri: {expected_kwh:,.1f} kWh")
            except Exception as e:
                st.error(f"Configurazione salvata, ma il calcolo è fallito: {e}")

        current_result = st.session_state.expected_results.get(sel_code)
        if current_result:
            if "error" in current_result:
                st.error(f"Ultimo calcolo fallito: {current_result['error']}")
            else:
                st.metric("Produzione attesa (ieri)", f"{current_result['expected_kwh']:,.1f} kWh")
                real_prod = sel_station.get("yesterday_kwh")
                if real_prod is not None and current_result["expected_kwh"]:
                    dev = (float(real_prod) - current_result["expected_kwh"]) / current_result["expected_kwh"] * 100
                    st.metric("Scostamento", f"{dev:+.1f}%")
                with st.expander("🛠️ Debug meteo/irraggiamento"):
                    st.json(current_result["raw_debug"])

        st.divider()
        n_configured = len(st.session_state.plant_config)
        st.caption(f"📋 Impianti configurati: **{n_configured}** / {len(stations_for_sidebar)}")
        if st.button("🔁 Ricalcola tutti i configurati", use_container_width=True):
            with st.spinner("Ricalcolo produzione attesa per tutti gli impianti configurati..."):
                calculate_expected_for_configured(stations_for_sidebar, force=True)
            st.success("Ricalcolo completato")


# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
stations = st.session_state.stations

if stations is not None:
    total = len(stations)
    total_capacity = sum(float(s.get("capacity") or 0) for s in stations)

    m1, m2, m3 = st.columns(3)
    with m1:
        render_html(f"""
        <div class="metric-card">
            <div class="metric-label">Impianti totali</div>
            <div class="metric-value metric-accent">{total}</div>
        </div>""")
    with m2:
        render_html(f"""
        <div class="metric-card">
            <div class="metric-label">Capacità totale installata</div>
            <div class="metric-value">{total_capacity:,.2f} <span style="font-size:16px;color:#8ea3b8;">kWp</span></div>
        </div>""")
    with m3:
        last_sync = time.strftime("%H:%M:%S", time.localtime(st.session_state.token_time))
        render_html(f"""
        <div class="metric-card">
            <div class="metric-label">Ultima sincronizzazione</div>
            <div class="metric-value" style="font-size:20px; font-family:'JetBrains Mono',monospace;">{last_sync}</div>
        </div>""")

    st.write("")
    search = st.text_input("🔍 Cerca impianto per nome, codice o indirizzo", "")

    filtered = stations
    if search:
        s_lower = search.lower()
        filtered = [
            s for s in stations
            if s_lower in str(s.get("stationName", "")).lower()
            or s_lower in str(s.get("stationCode", "")).lower()
            or s_lower in str(s.get("stationAddr", "")).lower()
        ]

    view_mode = st.radio("Visualizzazione", ["Schede", "Tabella"], horizontal=True, label_visibility="collapsed")

    st.write(f"**{len(filtered)}** impianti mostrati su {total}")

    has_status_data = any(s.get("health_state") is not None for s in stations)
    if has_status_data:
        n_alarm = sum(1 for s in stations if str(s.get("health_state")) == HEALTH_ALARM)
        n_disc = sum(1 for s in stations if str(s.get("health_state")) == HEALTH_DISCONNECTED)
        n_ok = sum(1 for s in stations if str(s.get("health_state")) == HEALTH_OK)
        st.markdown(
            f"<span class='led led-green'></span> {n_ok} OK &nbsp;&nbsp; "
            f"<span class='led led-red'></span> {n_alarm} in allarme &nbsp;&nbsp; "
            f"<span class='led led-gray'></span> {n_disc} disconnessi",
            unsafe_allow_html=True,
        )
        st.write("")

    if view_mode == "Schede":
        for s in filtered:
            name = s.get("stationName", "N/D")
            code = s.get("stationCode", "N/D")
            addr = s.get("stationAddr", "N/D")
            capacity = s.get("capacity", "N/D")

            health = str(s.get("health_state")) if s.get("health_state") is not None else None
            if health == HEALTH_ALARM:
                led_class, card_class = "led-red", "plant-card-alarm"
            elif health == HEALTH_DISCONNECTED:
                led_class, card_class = "led-gray", ""
            elif health == HEALTH_OK:
                led_class, card_class = "led-green", ""
            else:
                led_class, card_class = None, ""

            led_html = f'<span class="led {led_class}"></span>' if led_class else ""

            prod = s.get("yesterday_kwh")
            prod_html = ""
            if prod is not None:
                try:
                    prod_html = f'<span class="production-chip">🔋 Ieri: {float(prod):,.1f} kWh</span>'
                except (TypeError, ValueError):
                    prod_html = f'<span class="production-chip">🔋 Ieri: {prod}</span>'

            # --- Scostamento produzione reale vs attesa ---
            deviation_html = ""
            exp_result = st.session_state.expected_results.get(code)
            if exp_result and prod is not None:
                expected = exp_result.get("expected_kwh")
                if expected:
                    try:
                        dev_pct = (float(prod) - expected) / expected * 100
                        if dev_pct >= -8:
                            dev_class = "deviation-chip-ok"
                        elif dev_pct >= -20:
                            dev_class = "deviation-chip-warn"
                        else:
                            dev_class = "deviation-chip-bad"
                        sign = "+" if dev_pct >= 0 else ""
                        deviation_html = (
                            f'<span class="{dev_class}">📐 Attesa: {expected:,.1f} kWh '
                            f'· Scostamento: {sign}{dev_pct:.1f}%</span>'
                        )
                    except (TypeError, ValueError):
                        pass

            alarms_list = s.get("alarm_texts", [])
            alarm_html = ""
            if alarms_list:
                items = "".join(f"<li>{a}</li>" for a in alarms_list)
                alarm_html = f'<div class="alarm-box">🚨 <b>Allarmi rilevati:</b><ul style="margin:4px 0 0 18px; padding:0;">{items}</ul></div>'

            render_html(f"""
            <div class="plant-card {card_class}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div class="plant-name">{led_html}{name}<span class="plant-code">{code}</span></div>
                        <div class="plant-meta">
                            <span>📍 {addr}</span>
                            <span>⚡ {capacity} kWp</span>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        {prod_html}
                        {deviation_html}
                    </div>
                </div>
                {alarm_html}
            </div>
            """)

    else:
        # Visualizzazione Tabella
        table_data = []
        for s in filtered:
            code = s.get("stationCode", "")
            exp_res = st.session_state.expected_results.get(code, {})
            expected = exp_res.get("expected_kwh") if isinstance(exp_res, dict) else None
            
            real_prod = s.get("yesterday_kwh")
            dev_str = "N/D"
            if real_prod is not None and expected:
                try:
                    dev_pct = (float(real_prod) - float(expected)) / float(expected) * 100
                    dev_str = f"{dev_pct:+.1f}%"
                except Exception:
                    pass

            health_map = {HEALTH_OK: "🟢 OK", HEALTH_ALARM: "🔴 Allarme", HEALTH_DISCONNECTED: "⚪ Offline"}
            health_str = health_map.get(str(s.get("health_state")), "N/D")

            table_data.append({
                "Stato": health_str,
                "Nome Impianto": s.get("stationName"),
                "Codice": code,
                "Indirizzo": s.get("stationAddr"),
                "Potenza (kWp)": s.get("capacity"),
                "Produzione Ieri (kWh)": real_prod,
                "Produzione Attesa (kWh)": expected if expected else "N/D",
                "Scostamento": dev_str
            })
            
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)
