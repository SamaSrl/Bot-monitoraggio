import streamlit as st
import requests

st.set_page_config(page_title="FusionSolar - Test Endpoint Kiosk/KPI", page_icon="🔍")
st.title("🔍 Test Endpoint Monitoraggio")

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

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

if st.button("🚀 Esegui Test Kiosk/KPI", type="primary"):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. LOGIN
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    login_payload = {"username": API_USER, "password": API_PASS}

    res_login = session.post(login_url, json=login_payload, timeout=12)
    
    headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
    token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

    session.headers.update({
        "accessSession": token,
        "xsrf-token": token,
        "X-SRT": token
    })

    # ROTTE NORTHBOUND KIOSK E KPI
    endpoints_to_test = [
        f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationRealKpi",
        f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getDevList",
        f"{BASE_DOMAIN}/rest/pvms/v1/kiosk/getKioskRealKpi",
        f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getPlantList"
    ]

    for ep in endpoints_to_test:
        st.write(f"--- \n### Prova su: `{ep}`")
        try:
            res = session.post(ep, json={"pageNo": 1}, timeout=12)
            st.write(f"**Status Code:** `{res.status_code}`")
            try:
                data = res.json()
                if res.status_code == 200 and data.get("error_code") != "APIG.0101":
                    st.success("🎯 ENDPOINT TROVATO E FUNZIONANTE!")
                st.json(data)
            except Exception:
                st.code(res.text[:300], language="html")
        except Exception as e:
            st.error(f"Errore di connessione: {e}")
