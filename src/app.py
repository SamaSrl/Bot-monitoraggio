import streamlit as st
import requests
import time
import json
import os
import textwrap
import pandas as pd

st.set_page_config(page_title="FusionSolar Control Center", page_icon="🛰️", layout="wide")


def render_html(html):
    """st.markdown con unsafe_allow_html, ma prima rimuove l'indentazione
    Python della stringa: senza questo, le righe rientrate vengono a volte
    interpretate come blocchi di codice Markdown invece che come HTML,
    mostrando tag letterali (es. '</div>') invece di renderizzarli."""
    st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# CREDENZIALI — non hardcodare. Crea .streamlit/secrets.toml con:
# API_USER = "il_tuo_username_northbound"
# API_SYSTEM_CODE = "il_tuo_systemCode"
# ----------------------------------------------------------------------------
API_USER = st.secrets.get("API_USER", "")
API_SYSTEM_CODE = st.secrets.get("API_SYSTEM_CODE", "")
BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"
TOKEN_VALIDITY_SECONDS = 25 * 60  # rinnova login prima della scadenza reale (~30 min)

# ----------------------------------------------------------------------------
# CONFIGURAZIONE PERSISTENTE PER IMPIANTO (tilt, azimut, coordinate, PR)
# Salvata su file JSON accanto allo script: sopravvive a refresh e riavvii,
# perché st.session_state da solo si perderebbe ad ogni nuova sessione browser.
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
    """Effettua il login e restituisce una requests.Session autenticata."""
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
    """Riutilizza la sessione se ancora valida, altrimenti rifà login."""
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
        # se il token è scaduto, riprova con un login pulito una sola volta
        if data.get("failCode") in (407, 305) and not force:
            return fetch_stations(force=True)
        raise RuntimeError(data.get("message") or f"failCode {data.get('failCode')}")

    st.session_state.stations = data.get("data") or []
    return st.session_state.stations


def _chunk(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _post_kpi(session, endpoint, codes, extra_body=None, batch_size=100):
    """Chiama un endpoint KPI Huawei suddividendo stationCodes in batch (max ~100 per call).
    Ritorna una lista aggregata di record `data`."""
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


# Valori noti di real_health_state restituiti da getStationRealKpi:
# "1" = disconnesso, "2" = in allarme/guasto, "3" = sano/nessun allarme
HEALTH_OK = "3"
HEALTH_ALARM = "2"
HEALTH_DISCONNECTED = "1"


def fetch_health_and_yesterday_production(stations):
    """Arricchisce ogni stazione con: health_state, alarm_texts, yesterday_kwh."""
    session = get_authenticated_session()
    codes = [s.get("stationCode") for s in stations if s.get("stationCode")]
    if not codes:
        return stations

    # --- 1. Stato di salute / allarme in tempo reale ---
    health_by_code = {}
    try:
        kpi_data = _post_kpi(session, "/thirdData/getStationRealKpi", codes)
        for rec in kpi_data:
            code = rec.get("stationCode")
            item = rec.get("dataItemMap", {}) or {}
            health_by_code[code] = item.get("real_health_state")
    except Exception as e:
        st.warning(f"⚠️ Impossibile recuperare lo stato di salute impianti: {e}")

    # --- 2. Dettaglio allarmi (solo per impianti non sani, per risparmiare chiamate) ---
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

    # --- 3. Produzione di ieri ---
    # L'endpoint "getKpiStationDay" si è rivelato inaffidabile: a volte
    # restituisce il cumulato parziale di OGGI invece del totale di ieri.
    # Per essere sicuri sommiamo noi stessi i valori ORARI ("getKpiStationHour")
    # dell'intera giornata di ieri, verificando che ogni collectTime orario
    # ricada davvero nel giorno richiesto.
    prod_by_code = {}
    raw_kpi_by_code = {}
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime, timedelta

        rome = ZoneInfo("Europe/Rome")
        now_rome = datetime.now(rome)
        yesterday_date = (now_rome - timedelta(days=1)).date()
        y_midnight = datetime(yesterday_date.year, yesterday_date.month, yesterday_date.day,
                               0, 0, 0, tzinfo=rome)
        y_end = y_midnight + timedelta(days=1)
        collect_time_ms = int(y_midnight.timestamp() * 1000)
        st.session_state["_debug_collect_time"] = (
            f"giorno richiesto: {yesterday_date.isoformat()} "
            f"(collectTime={collect_time_ms})"
        )

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

            # teniamo solo i punti orari che ricadono davvero nel giorno "ieri"
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
    """Calcola la produzione attesa di ieri usando l'irraggiamento sul piano
    inclinato (Global Tilted Irradiance) di Open-Meteo, dati tilt/azimut reali
    dell'impianto. Convenzione azimut Open-Meteo: 0=Sud, -90=Est, +90=Ovest
    (stessa convenzione tipicamente usata in Italia per gli impianti FV).

    Ritorna (expected_kwh, raw_hourly_debug).
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime, timedelta

    rome = ZoneInfo("Europe/Rome")
    yesterday = (datetime.now(rome) - timedelta(days=1)).date().isoformat()

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
        # GTI è una media oraria in W/m²: diviso 1000 (STC) * kWp * PR = kWh per quell'ora
        total_kwh += (gti / 1000.0) * capacity_kwp * performance_ratio

    debug = {
        "date": yesterday,
        "n_hourly_points": len(times),
        "hourly_time": times,
        "hourly_gti_w_m2": gti_values,
    }
    return round(total_kwh, 2), debug


# ----------------------------------------------------------------------------
# CARICAMENTO AUTOMATICO — impianti + stato + allarmi + produzione di ieri
# vengono caricati da soli all'apertura della pagina, senza bisogno di bottoni.
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

    st.session_state.auto_loaded = True

# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
stations = st.session_state.stations

if stations is not None:
    total = len(stations)
    total_capacity = sum(float(s.get("capacity") or 0) for s in stations)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Impianti totali</div>
            <div class="metric-value metric-accent">{total}</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Capacità totale installata</div>
            <div class="metric-value">{total_capacity:,.2f} <span style="font-size:16px;color:#8ea3b8;">kWp</span></div>
        </div>""", unsafe_allow_html=True)
    with m3:
        last_sync = time.strftime("%H:%M:%S", time.localtime(st.session_state.token_time))
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ultima sincronizzazione</div>
            <div class="metric-value" style="font-size:20px; font-family:'JetBrains Mono',monospace;">{last_sync}</div>
        </div>""", unsafe_allow_html=True)

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
            grid_date = s.get("gridConnectionDate", "N/D")

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

            # --- Scostamento produzione reale vs attesa (se già calcolato) ---
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
                    except (TypeError, ZeroDivisionError):
                        pass

            alarms = s.get("alarm_texts") or []
            alarm_html = ""
            if alarms:
                alarm_list = "".join(f"⚠️ {a}<br>" for a in alarms[:5])
                alarm_html = f'<div class="alarm-box">{alarm_list}</div>'

            st.markdown(f"""
            <div class="plant-card {card_class}">
                {led_html}<span class="plant-name">☀️ {name}</span><span class="plant-code">{code}</span>
                <div class="plant-meta">
                    <span>📍 {addr}</span>
                    <span>⚡ {capacity} kWp</span>
                    <span>📅 Connesso: {grid_date}</span>
                    {prod_html}
                    {deviation_html}
                </div>
                {alarm_html}
            </div>
            """, unsafe_allow_html=True)

            # --- Configurazione orientamento (tilt/azimut/coordinate) + calcolo scostamento ---
            saved_cfg = st.session_state.plant_config.get(code, {})
            default_lat = saved_cfg.get("lat") or s.get("latitude") or s.get("stationLatitude") or 0.0
            default_lon = saved_cfg.get("lon") or s.get("longitude") or s.get("stationLongitude") or 0.0

            with st.expander(f"⚙️ Configura orientamento — {name}"):
                cfg_col1, cfg_col2, cfg_col3, cfg_col4 = st.columns(4)
                with cfg_col1:
                    tilt_val = st.number_input(
                        "Tilt (°)", min_value=0.0, max_value=90.0,
                        value=float(saved_cfg.get("tilt", 30.0)), step=1.0, key=f"tilt_{code}",
                        help="Inclinazione dei pannelli rispetto all'orizzontale"
                    )
                with cfg_col2:
                    azimuth_val = st.number_input(
                        "Azimut (°)", min_value=-180.0, max_value=180.0,
                        value=float(saved_cfg.get("azimuth", 0.0)), step=1.0, key=f"az_{code}",
                        help="0 = Sud, -90 = Est, +90 = Ovest, ±180 = Nord"
                    )
                with cfg_col3:
                    lat_val = st.number_input(
                        "Latitudine", value=float(default_lat), format="%.6f", key=f"lat_{code}"
                    )
                with cfg_col4:
                    lon_val = st.number_input(
                        "Longitudine", value=float(default_lon), format="%.6f", key=f"lon_{code}"
                    )
                pr_val = st.slider(
                    "Performance Ratio (perdite di sistema)", min_value=0.50, max_value=1.00,
                    value=float(saved_cfg.get("pr", 0.80)), step=0.01, key=f"pr_{code}",
                    help="Tiene conto di perdite da inverter, cablaggio, temperatura, sporcizia. Tipico: 0.75–0.85"
                )

                save_col, calc_col = st.columns(2)
                with save_col:
                    if st.button("💾 Salva configurazione", key=f"save_{code}"):
                        st.session_state.plant_config[code] = {
                            "tilt": tilt_val, "azimuth": azimuth_val,
                            "lat": lat_val, "lon": lon_val, "pr": pr_val,
                        }
                        save_plant_config(st.session_state.plant_config)
                        st.success("Configurazione salvata ✅")

                with calc_col:
                    if st.button("📊 Calcola scostamento produzione", key=f"calc_{code}"):
                        try:
                            cap = float(capacity) if capacity not in (None, "N/D") else None
                            expected_kwh, raw_debug = get_expected_production_yesterday(
                                lat_val, lon_val, tilt_val, azimuth_val, cap, pr_val
                            )
                            st.session_state.expected_results[code] = {
                                "expected_kwh": expected_kwh, "raw_debug": raw_debug
                            }
                            st.success(f"Produzione attesa ieri: {expected_kwh:,.1f} kWh")
                        except Exception as e:
                            st.error(f"Errore nel calcolo: {e}")

                if code in st.session_state.expected_results:
                    with st.expander("🛠️ Debug meteo/irraggiamento"):
                        st.json(st.session_state.expected_results[code]["raw_debug"])
    else:
        df = pd.DataFrame(filtered)
        if has_status_data:
            df["health_state"] = df.get("health_state")
            df["alarm_texts"] = df.get("alarm_texts", pd.Series([[]] * len(df))).apply(
                lambda x: "; ".join(x) if isinstance(x, list) else x
            )
        cols_priority = ["stationCode", "stationName", "stationAddr", "capacity",
                          "gridConnectionDate", "health_state", "alarm_texts", "yesterday_kwh"]
        ordered_cols = [c for c in cols_priority if c in df.columns] + [c for c in df.columns if c not in cols_priority]
        st.dataframe(df[ordered_cols], use_container_width=True, height=500)

    if has_status_data:
        with st.expander("🛠️ Debug: dati grezzi stato/produzione (per verificare i nomi dei campi)"):
            st.markdown(f"**{st.session_state.get('_debug_collect_time', 'N/D')}**")
            st.caption("`yesterday_kwh_estratto` è la SOMMA dei valori orari (`getKpiStationHour`) "
                       "ricadenti nel giorno richiesto. `_raw_kpi` mostra tutti i singoli punti orari "
                       "usati nel calcolo: controlla che siano ~24 e che le date/ore abbiano senso "
                       "(es. valori diversi da zero solo nelle ore di luce).")
            st.json([
                {
                    "stationCode": s.get("stationCode"),
                    "stationName": s.get("stationName"),
                    "health_state": s.get("health_state"),
                    "alarm_texts": s.get("alarm_texts"),
                    "yesterday_kwh_estratto": s.get("yesterday_kwh"),
                    "n_punti_orari": len(s.get("_raw_kpi") or []),
                    "_raw_kpi": s.get("_raw_kpi"),
                }
                for s in filtered[:10]
            ])

else:
    st.info("Caricamento in corso o credenziali mancanti — controlla eventuali errori sopra.")
