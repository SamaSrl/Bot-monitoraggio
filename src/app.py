import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Test Regionale", page_icon="🌐", layout="wide")
st.title("🌐 FusionSolar - Test Server Regionali Huawei")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

# Domini dei vari server regionali Huawei FusionSolar
DOMAINS = [
    "https://eu5.fusionsolar.huawei.com",
    "https://intl.fusionsolar.huawei.com",
    "https://region01.fusionsolar.huawei.com",
    "https://region02.fusionsolar.huawei.com",
    "https://sg5.fusionsolar.huawei.com",
]

if st.button("🚀 Esegui Test Multi-Server", type="primary"):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    found = False

    for domain in DOMAINS:
        st.markdown(f"--- \n### Prova su: `{domain}`")
        try:
            # 1. Login
            login_url = f"{domain}/rest/openapi/pvms/v1/login"
            res_login = session.post(login_url, json={"username": API_USER, "password": API_PASS}, timeout=8)
            
            st.write(f"**Status Code Login:** `{res_login.status_code}`")
            if res_login.status_code != 200:
                st.warning("⚠️ Login fallito o non supportato su questo host.")
                continue

            headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
            token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

            if not token:
                st.warning("⚠️ Login OK ma nessun token restituito.")
                continue

            st.success(f"🔑 Login riuscito! Token: `{token[:15]}...`")

            # Update Session Headers
            session.headers.update({
                "accessSession": token,
                "xsrf-token": token,
                "X-SRT": token
            })

            # 2. Test Stazioni
            station_url = f"{domain}/rest/openapi/pvms/v1/getStationList"
            res_stations = session.post(station_url, json={"pageNo": 1, "pageSize": 100}, timeout=8)
            
            st.write(f"**Status Code Stazioni:** `{res_stations.status_code}`")

            if res_stations.status_code == 200:
                data = res_stations.json()
                if data.get("error_code") != "APIG.0101":
                    st.success(f"🎯 **SERVER CORRETTO TROVATO: {domain}**")
                    st.json(data)
                    found = True
                    break
                else:
                    st.error("❌ Errore APIG.0101 (API non pubblicata su questo cluster)")
            else:
                st.error(f"❌ Errore HTTP {res_stations.status_code}")

        except Exception as e:
            st.error(f"Errore durante la connessione: {e}")

    if not found:
        st.info("💡 Se tutti i server danno APIG.0101, il gateway Huawei sta ancora aggiornando i permessi salvati sul portale (può richiedere fino a 15 minuti).")
