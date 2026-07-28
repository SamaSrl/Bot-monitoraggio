import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Lista Impianti", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Step 1: Lista Impianti")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

# Header di sistema per evitare blocchi o "N/A" da parte dei server Huawei
HEADERS_BASE = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "clientType": "0"
}

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update(HEADERS_BASE)

    # 1. LOGIN
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    login_payload = {"username": username, "password": password}

    try:
        res_login = session.post(login_url, json=login_payload, timeout=12)
    except Exception as e:
        return None, f"Errore di rete/connessione: {e}"

    if res_login.status_code != 200:
        return None, f"Login fallito con Status Code {res_login.status_code}: {res_login.text}"

    login_data = res_login.json()
    if not login_data.get("success"):
        return None, f"Login rifiutato da Huawei: {login_data.get('message')} (Codice: {login_data.get('failCode')})"

    # Estrazione Token XSRF dagli Header o dai Cookie
    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

    if not token:
        return None, "Login riuscito ma token XSRF non trovato nella risposta."

    # Impostazione Header per le API Gateway Huawei
    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "XSRF-TOKEN": token,
        "X-SRT": token
    })

    # 2. RECUPERO LISTA STAZIONI
    station_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList"
    
    try:
        res_stations = session.post(station_url, json={"pageNo": 1, "pageSize": 100}, timeout=12)
    except Exception as e:
        return None, f"Errore di rete durante il recupero stazioni: {e}"

    if res_stations.status_code != 200:
        return None, f"Errore HTTP Stazioni ({res_stations.status_code}): {res_stations.text}"

    data = res_stations.json()
    if not data.get("success"):
        return None, f"Errore API Stazioni: {data.get('message')} (Codice: {data.get('failCode')})"

    stations = data.get("data", [])
    if isinstance(stations, dict):
        stations = stations.get("list", [])

    return stations, None


if st.button("🔄 Connetti e Carica Impianti", type="primary"):
    st.cache_data.clear()

with st.spinner("Autenticazione e recupero impianti in corso..."):
    stations, err = get_huawei_stations(API_USER, API_PASS)

if err:
    st.error(f"⚠️ {err}")
elif stations is not None:
    st.success(f"🎉 Connessione riuscita! Trovati **{len(stations)}** impianti associati.")
    df_stations = pd.DataFrame(stations)
    
    # Visualizzazione pulita delle colonne principali se presenti
    cols = [c for c in ["stationCode", "stationName", "capacity", "buildState"] if c in df_stations.columns]
    if cols:
        st.dataframe(df_stations[cols], use_container_width=True)
    else:
        st.dataframe(df_stations, use_container_width=True)
