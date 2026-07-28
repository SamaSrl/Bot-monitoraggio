import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="FusionSolar - Accesso Diretto", page_icon="☀️", layout="wide")
st.title("☀️ FusionSolar - Connessione Flusso Portal / Solarfox")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

if st.button("🚀 Connetti con Flusso Portal", type="primary"):
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "clientType": "0"
    })

    st.subheader("1. Autenticazione Sessione")
    login_url = f"{BASE_DOMAIN}/rest/pvms/web/login" # Endpoint di login usato dal portale/integrazioni
    
    # Se il primo fallisce, proviamo l'endpoint openapi standard
    try:
        res_login = session.post(login_url, json={"username": API_USER, "password": API_PASS}, timeout=10)
        if res_login.status_code != 200:
            login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
            res_login = session.post(login_url, json={"username": API_USER, "password": API_PASS}, timeout=10)
            
        st.write(f"**Status Login:** `{res_login.status_code}`")
        
        # Recupero Token di Sessione
        token = res_login.cookies.get("XSRF-TOKEN") or res_login.headers.get("xsrf-token")
        if not token:
            headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
            token = headers_lower.get("xsrf-token")
            
        st.info(f"Token estratto: `{token}`")
        
        # Impostiamo tutti gli header necessari per emulare la sessione attiva
        session.headers.update({
            "xsrf-token": token,
            "XSRF-TOKEN": token,
            "roaming-token": token,
            "accessSession": token
        })

    except Exception as e:
        st.error(f"Errore durante il login: {e}")
        st.stop()

    st.markdown("---")
    st.subheader("2. Recupero Impianti (Rotte Portal & OpenAPI Client)")

    # Proviamo la sequenza di endpoint usati dai connettori terzi
    endpoints_to_test = [
        # Endpoint usati dal portale web e dai connettori Solarfox/HomeAssistant
        ("/rest/pvms/web/station/v1/overview/station-list", {"pageNo": 1, "pageSize": 100}),
        ("/rest/pvms/web/building/v1/station/list", {"pageNo": 1, "pageSize": 100}),
        ("/rest/openapi/pvms/v1/getStationList", {"pageNo": 1, "pageSize": 100}),
        ("/unishare/redirect/getStationList", {"pageNo": 1, "pageSize": 100})
    ]

    success_data = None
    working_ep = None

    for ep, payload in endpoints_to_test:
        url = f"{BASE_DOMAIN}{ep}"
        st.write(f"Testing: `{ep}` ...")
        
        try:
            res = session.post(url, json=payload, timeout=8)
            st.write(f"-> Status: `{res.status_code}`")
            
            if res.status_code == 200:
                data = res.json()
                # Verifichiamo se abbiamo una risposta valida priva dell'errore APIG.0101
                if data.get("error_code") != "APIG.0101" and (data.get("success") == True or "data" in data or "list" in data):
                    success_data = data
                    working_ep = ep
                    break
                else:
                    st.caption(f"Risposta: {data}")
            else:
                st.caption(f"Errore HTTP: {res.text[:100]}")
        except Exception as ex:
            st.caption(f" Eccezione: {ex}")

    st.markdown("---")
    if working_ep:
        st.balloons()
        st.success(f"🎉 **CONNESSO CON SUCCESSO tramite la rotta:** `{working_ep}`")
        st.json(success_data)
    else:
        st.warning("⚠️ Nessuno degli endpoint di sessione ha restituito i dati direttamente. Esaminiamo i log qui sopra per sbloccare la chiamata precisa.")
