import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Lista Impianti", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Step 1: Lista Impianti")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. Login Northbound API
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    login_payload = {
        "username": username,
        "password": password
    }
    
    res_login = session.post(login_url, json=login_payload, timeout=12)
    
    if res_login.status_code != 200:
        return None, f"Errore HTTP Login: {res_login.status_code}", None

    # Estrazione Token XSRF
    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

    if not token:
        return None, "Impossibile recuperare il token di autenticazione.", None

    # Impostazione Header per Huawei APIG (Tutti i formati accettati)
    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "XSRF-TOKEN": token,
        "X-SRT": token
    })

    # VARIANTI DI ENDPOINT USATE NELLE APIS NORTHBOUND V6 / THIRDPARTY
    endpoints_to_try = [
        f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList",
        f"{BASE_DOMAIN}/thirdparty/getStationList",
        f"{BASE_DOMAIN}/rest/openapi/getStationList",
        f"{BASE_DOMAIN}/thirdparty/open/getStationList",
        f"{BASE_DOMAIN}/rest/pvms/v1/openapi/getStationList"
    ]

    last_response = None
    
    for ep in endpoints_to_try:
        try:
            res_stations = session.post(ep, json={"pageNo": 1, "pageSize": 100}, timeout=12)
            last_response = res_stations.text
            
            if res_stations.status_code == 200:
                data = res_stations.json()
                # Se non restituisce l'errore APIG.0101, abbiamo trovato la rotta corretta!
                if data.get("error_code") != "APIG.0101":
                    stations_data = data.get("data", [])
                    if isinstance(stations_data, dict):
                        stations_data = stations_data.get("list", [])
                    return stations_data, None, ep
        except Exception:
            continue

    return None, f"Nessun endpoint valido risponde. Ultima risposta: {last_response}", None


if st.button("🔄 Connetti e Carica Impianti", type="primary"):
    st.cache_data.clear()

with st.spinner("Ricerca endpoint e recupero impianti in corso..."):
    stations, err, working_ep = get_huawei_stations(API_USER, API_PASS)

if err:
    st.error(f"⚠️ {err}")
elif stations is not None:
    st.success(f"🎉 Connessione riuscita! Rotta attiva: `{working_ep}`. Trovati **{len(stations)}** impianti.")
    df_stations = pd.DataFrame(stations)
    st.dataframe(df_stations, use_container_width=True)
