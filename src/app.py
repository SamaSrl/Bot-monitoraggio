import streamlit as st
import requests

st.set_page_config(page_title="FusionSolar - Test Token", page_icon="🔑")
st.title("🔑 Diagnostica Token Login")

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

if st.button("🚀 Esegui Test Login Pulito", type="primary"):
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    
    login_url = f"{HUAWEI_BASE_URL}/login"
    login_payload = {"username": API_USER, "password": API_PASS}
    
    try:
        res = session.post(login_url, json=login_payload, headers=headers, timeout=12)
        
        st.write("### 1. Risposta JSON del Login:")
        st.json(res.json())
        
        st.write("### 2. Header della Risposta:")
        st.json(dict(res.headers))

        st.write("### 3. Cookie salvati nel client:")
        st.json(session.cookies.get_dict())

    except Exception as e:
        st.error(f"Errore durante la connessione: {e}")
