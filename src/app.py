import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Lista Impianti", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Step 1: Lista Impianti")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "clientType": "0"
}

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update(HEADERS_BASE)

    # 1. Login
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    res_login = session.post(login_url, json={"username": username, "password": password}, timeout=12)
    
    if res_login.status_code != 200:
        return None, f"Errore HTTP Login ({res_login.status_code}): {res_login.text}"

    # Token Extraction
    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

    if not token:
        return None, "Token XSRF non trovato."

    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "XSRF-TOKEN": token
    })

    # 2. Chiamata getStationList
    endpoint = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList"
    res = session.post(endpoint, json={"pageNo": 1, "pageSize": 100}, timeout=12)

    if res.status_code != 200:
        # Tentativo Fallback su getPlantList
        endpoint_alt = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getPlantList"
        res_alt = session.post(endpoint_alt, json={"pageNo": 1, "pageSize": 100}, timeout=12)
        if res_alt.status_code == 200:
            res = res_alt
        else:
            return None, f"Errore HTTP ({res.status_code}): {res.text}"

    data = res.json()
    if not data.get("success"):
        return None, f"Errore API Huawei: {data.get('message')} (Codice: {data.get('failCode')})"

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
    st.dataframe(df_stations, use_container_width=True)
