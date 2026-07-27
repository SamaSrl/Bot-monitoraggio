import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Impianti", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Lista Impianti Collegati")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. Login Northbound API
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    res_login = session.post(login_url, json={"username": username, "password": password}, timeout=12)
    
    if res_login.status_code != 200:
        return None, f"Errore HTTP Login: {res_login.status_code}"

    # Estrazione Token XSRF
    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

    if not token:
        return None, "Impossibile recuperare il token di autenticazione."

    # Inserimento Header di Sessione
    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "X-SRT": token
    })

    # 2. Chiamata getStationList con Paginazione Corretta
    station_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList"
    res_stations = session.post(station_url, json={"pageNo": 1, "pageSize": 100}, timeout=12)
    
    if res_stations.status_code != 200:
        return None, f"Errore HTTP Stazioni ({res_stations.status_code}): {res_stations.text}"

    data = res_stations.json()
    if not data.get("success"):
        return None, f"Errore API Huawei: {data.get('message')} (Codice: {data.get('failCode')})"

    # Estrazione Lista Impianti
    stations_data = data.get("data", [])
    if isinstance(stations_data, dict):
        stations_data = stations_data.get("list", [])

    return stations_data, None


if st.button("🔄 Connetti e Carica Impianti", type="primary"):
    st.cache_data.clear()

with st.spinner("Autenticazione e recupero impianti in corso..."):
    stations, err = get_huawei_stations(API_USER, API_PASS)

if err:
    st.error(f"⚠️ {err}")
elif stations is not None:
    st.success(f"🎉 Connessione riuscita! Trovati **{len(stations)}** impianti associati.")
    
    # Tabella Pulita degli Impianti
    df_stations = pd.DataFrame(stations)
    
    # Selezione colonne principali se presenti
    cols_to_show = [c for c in ["stationCode", "stationName", "capacity", "buildState"] if c in df_stations.columns]
    if cols_to_show:
        st.dataframe(df_stations[cols_to_show], use_container_width=True)
    else:
        st.dataframe(df_stations, use_container_width=True)
