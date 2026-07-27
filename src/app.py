import streamlit as st
import pandas as pd
import requests

# Configurazione Pagina
st.set_page_config(page_title="FusionSolar - Step 1", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Step 1: Login & Lista Impianti")

# Recupero Credenziali
API_USER = (
    st.secrets.get("huawei", {}).get("username")
    or st.secrets.get("username")
    or st.secrets.get("FUSIONSOLAR_USERNAME", "Monitoragg_api")
)

API_PASS = (
    st.secrets.get("huawei", {}).get("password")
    or st.secrets.get("password")
    or st.secrets.get("FUSIONSOLAR_PASSWORD", "")
)

# Base URL per EU5
BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. LOGIN
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    login_payload = {"username": username, "password": password}

    try:
        res_login = session.post(login_url, json=login_payload, timeout=12)
        if res_login.status_code != 200:
            return None, f"Errore HTTP Login: {res_login.status_code}", None

        # Estrazione token
        headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
        token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

        if not token:
            return None, "Impossibile estrarre il token dalla risposta di Login.", None

        # Header sessione per Huawei APIG
        session.headers.update({
            "accessSession": token,
            "xsrf-token": token,
            "X-SRT": token
        })

        # 2. PROVA ENDPOINT 1 (Standard OpenAPI PVMS)
        endpoint_1 = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList"
        res_list = session.post(endpoint_1, json={"pageNo": 1}, timeout=12)
        data_list = res_list.json()

        # Se dà errore APIG.0101 (API non esistente), proviamo l'ENDPOINT 2 (Thirdparty API)
        if data_list.get("error_code") == "APIG.0101":
            endpoint_2 = f"{BASE_DOMAIN}/thirdparty/station/list"
            res_list = session.post(endpoint_2, json={"pageNo": 1, "pageSize": 100}, timeout=12)
            data_list = res_list.json()

        # Se dà ancora APIG.0101, proviamo l'ENDPOINT 3 (OpenAPI v1 generico)
        if data_list.get("error_code") == "APIG.0101":
            endpoint_3 = f"{BASE_DOMAIN}/rest/openapi/pv/v1/station/list"
            res_list = session.post(endpoint_3, json={"pageNo": 1}, timeout=12)
            data_list = res_list.json()

        # Estrazione stazioni
        stations = []
        if isinstance(data_list.get("data"), list):
            stations = data_list.get("data")
        elif isinstance(data_list.get("data"), dict):
            stations = data_list.get("data", {}).get("list", [])

        if not data_list.get("success") and not stations:
            msg = data_list.get("message") or data_list.get("error_msg") or "Risposta senza campo success"
            code = data_list.get("failCode") or data_list.get("error_code") or "N/D"
            return None, f"Errore API Stazioni: {msg} (Code: {code})", data_list

        return stations, None, data_list

    except Exception as e:
        return None, f"Errore di connessione: {e}", None


# TEST ED ESECUZIONE
if API_PASS:
    if st.button("🔄 Connetti e Carica Impianti", type="primary"):
        st.cache_data.clear()

    with st.spinner("Autenticazione e ricerca percorsi API in corso..."):
        stations, err, raw_json = get_huawei_stations(API_USER, API_PASS)

    if err:
        st.error(f"⚠️ {err}")
        if raw_json:
            st.markdown("**Risposta RAW ricevuta da Huawei:**")
            st.json(raw_json)
    elif stations is not None:
        st.success(f"🎉 Connessione riuscita! Trovati **{len(stations)}** impianti.")
        
        # Mostra la tabella degli impianti
        df_stations = pd.DataFrame(stations)
        st.dataframe(df_stations, use_container_width=True)
else:
    st.error("⚠️ Password non trovata nei Secrets.")
