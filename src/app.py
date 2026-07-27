import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Step 1", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Step 1: Lista Impianti")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

def try_v1_api(session, username, password):
    # Login V1 Standard
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    res_login = session.post(login_url, json={"username": username, "password": password}, timeout=10)
    
    if res_login.status_code != 200:
        return None, f"Login V1 fallito HTTP {res_login.status_code}"

    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")
    
    if not token:
        return None, "Token V1 non trovato"

    # Header V1
    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "XSRF-TOKEN": token
    })

    # Chiamata V1
    res = session.post(f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList", json={"pageNo": 1, "pageSize": 100}, timeout=10)
    return res, "V1 (/rest/openapi/pvms/v1/getStationList)"

def try_thirdparty_api(session, username, password):
    # Login Thirdparty / V6
    login_url = f"{BASE_DOMAIN}/thirdparty/login"
    res_login = session.post(login_url, json={"username": username, "password": password}, timeout=10)
    
    if res_login.status_code != 200:
        return None, f"Login Thirdparty fallito HTTP {res_login.status_code}"

    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")
    
    if not token:
        return None, "Token Thirdparty non trovato"

    # Header Thirdparty
    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "XSRF-TOKEN": token
    })

    # Chiamata Thirdparty
    res = session.post(f"{BASE_DOMAIN}/thirdparty/getStationList", json={"pageNo": 1, "pageSize": 100}, timeout=10)
    return res, "Thirdparty (/thirdparty/getStationList)"


if st.button("🔄 Connetti e Carica Impianti", type="primary"):
    st.cache_data.clear()

with st.spinner("Autenticazione e test architetture API in corso..."):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Prova 1: OpenAPI V1 Standard
    res_v1, label_v1 = try_v1_api(session, API_USER, API_PASS)
    
    stations = None
    err = None
    working_label = ""

    if res_v1 and res_v1.status_code == 200:
        data = res_v1.json()
        if data.get("error_code") != "APIG.0101":
            stations = data.get("data", [])
            working_label = label_v1

    # Prova 2: Thirdparty V6 (se V1 ha dato APIG.0101 o errored)
    if not stations:
        session_tp = requests.Session()
        session_tp.headers.update({"Content-Type": "application/json"})
        res_tp, label_tp = try_thirdparty_api(session_tp, API_USER, API_PASS)
        
        if res_tp and res_tp.status_code == 200:
            data = res_tp.json()
            if data.get("error_code") != "APIG.0101":
                stations = data.get("data", [])
                working_label = label_tp
            else:
                err = f"Entrambe le architetture rispondono APIG.0101. RAW V1: {res_v1.text} | RAW TP: {res_tp.text}"
        else:
            raw_v1 = res_v1.text if res_v1 else "N/A"
            raw_tp = res_tp.text if res_tp else "N/A"
            err = f"Impossibile accedere. Risposta V1: {raw_v1} | Risposta Thirdparty: {raw_tp}"

if err:
    st.error(f"⚠️ {err}")
elif stations is not None:
    if isinstance(stations, dict):
        stations = stations.get("list", [])
        
    st.success(f"🎉 Connessione riuscita via **{working_label}**! Trovati **{len(stations)}** impianti.")
    df_stations = pd.DataFrame(stations)
    st.dataframe(df_stations, use_container_width=True)
