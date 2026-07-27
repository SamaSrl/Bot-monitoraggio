import streamlit as st
import requests

st.set_page_config(page_title="FusionSolar - Ispezione Lista Stazioni", page_icon="🔍")
st.title("🔍 Ispezione Risposta Stazioni")

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

if st.button("🚀 Leggi Risposta RAW Lista Stazioni", type="primary"):
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

    # 2. CHIAMATA AGLI ENDPOINT
    endpoints = [
        f"{BASE_DOMAIN}/thirdparty/station/list",
        f"{BASE_DOMAIN}/rest/openapi/pvms/v1/getStationList"
    ]

    for ep in endpoints:
        st.write(f"--- \n### Prova su Endpoint: `{ep}`")
        try:
            res = session.post(ep, json={"pageNo": 1, "pageSize": 100}, timeout=12)
            st.write(f"**Status Code:** {res.status_code}")
            try:
                st.json(res.json())
            except Exception:
                st.text(res.text)
        except Exception as e:
            st.error(f"Errore nella chiamata: {e}")
