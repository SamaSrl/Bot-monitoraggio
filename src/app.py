import streamlit as st
import requests
import json

st.set_page_config(page_title="FusionSolar Debug", page_icon="🔍")
st.title("🔍 FusionSolar - Diagnostica Login & API")

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

if st.button("🚀 Esegui Test Diagnostico API", type="primary"):
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    
    st.write("### 1. Invio richiesta di Login...")
    login_url = f"{HUAWEI_BASE_URL}/login"
    login_payload = {"username": API_USER, "password": API_PASS}
    
    try:
        res = session.post(login_url, json=login_payload, headers=headers, timeout=12)
        st.write(f"**HTTP Status Code:** `{res.status_code}`")
        
        # Stampa JSON del Login
        try:
            login_json = res.json()
            st.write("**Body JSON restituito da /login:**")
            st.json(login_json)
        except Exception as e:
            st.error(f"Impossibile leggere il JSON di login: {e}")
            st.text(res.text)

        st.write("**Header di risposta ricevuti:**")
        st.json(dict(res.headers))

        st.write("**Cookie salvati nella sessione:**")
        st.json(session.cookies.get_dict())

    except Exception as e:
        st.error(f"Errore durante la connessione: {e}")
