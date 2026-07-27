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

HUAWEI_BASE_URL = "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1"

@st.cache_data(ttl=900, show_spinner=False)
def get_huawei_stations(username, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. LOGIN
    login_url = f"{HUAWEI_BASE_URL}/login"
    login_payload = {"username": username, "password": password}

    try:
        res_login = session.post(login_url, json=login_payload, timeout=12)
        if res_login.status_code != 200:
            return None, f"Errore HTTP Login: {res_login.status_code}", None

        # Estrazione del token dagli header/cookie
        headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
        token = (
            headers_lower.get("xsrf-token")
            or session.cookies.get("XSRF-TOKEN")
        )

        if not token:
            return None, "Impossibile estrarre il token dalla risposta di Login.", None

        # Passiamo l'accessSession e gli header correlati
        session.headers.update({
            "accessSession": token,
            "xsrf-token": token,
            "X-SRT": token
        })

        # 2. RECUPERO LISTA STAZIONI (Con paginazione obbligatoria)
        # L'API OpenAPI richiede pageNo
        res_list = session.post(f"{HUAWEI_BASE_URL}/getStationList", json={"pageNo": 1}, timeout=12)
        data_list = res_list.json()

        # Estrazione stazioni o dati
        stations = []
        if isinstance(data_list.get("data"), list):
            stations = data_list.get("data")
        elif isinstance(data_list.get("data"), dict):
            stations = data_list.get("data", {}).get("list", [])

        if not data_list.get("success") and not stations:
            msg = data_list.get("message") or "Risposta senza campo success"
            code = data_list.get("failCode", "N/D")
            return None, f"Errore API Stazioni: {msg} (Code: {code})", data_list

        return stations, None, data_list

    except Exception as e:
        return None, f"Errore di connessione: {e}", None


# TEST ED ESECUZIONE
if API_PASS:
    if st.button("🔄 Connetti e Carica Impianti", type="primary"):
        st.cache_data.clear()

    with st.spinner("Autenticazione e recupero impianti in corso..."):
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
