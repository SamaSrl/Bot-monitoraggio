import streamlit as st
import requests
import time
import pandas as pd

st.set_page_config(page_title="FusionSolar Control Center", page_icon="🛰️", layout="wide")

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


# ----------------------------------------------------------------------------
# CONTROLS
# ----------------------------------------------------------------------------
col_a, col_b, col_c = st.columns([1, 1, 4])
with col_a:
    load_clicked = st.button("⚡ Carica impianti", type="primary")
with col_b:
    refresh_clicked = st.button("🔄 Forza refresh")

if load_clicked or refresh_clicked:
    with st.spinner("Connessione al gateway FusionSolar..."):
        try:
            fetch_stations(force=refresh_clicked)
        except Exception as e:
            st.error(f"❌ Errore: {e}")

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

    if view_mode == "Schede":
        for s in filtered:
            name = s.get("stationName", "N/D")
            code = s.get("stationCode", "N/D")
            addr = s.get("stationAddr", "N/D")
            capacity = s.get("capacity", "N/D")
            grid_date = s.get("gridConnectionDate", "N/D")

            st.markdown(f"""
            <div class="plant-card">
                <span class="plant-name">☀️ {name}</span><span class="plant-code">{code}</span>
                <div class="plant-meta">
                    <span>📍 {addr}</span>
                    <span>⚡ {capacity} kWp</span>
                    <span>📅 Connesso: {grid_date}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        df = pd.DataFrame(filtered)
        cols_priority = ["stationCode", "stationName", "stationAddr", "capacity", "gridConnectionDate"]
        ordered_cols = [c for c in cols_priority if c in df.columns] + [c for c in df.columns if c not in cols_priority]
        st.dataframe(df[ordered_cols], use_container_width=True, height=500)

else:
    st.info("👆 Premi **Carica impianti** per connetterti al gateway ed elencare tutti gli impianti disponibili.")
