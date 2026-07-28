import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Route Scanner", page_icon="📡", layout="wide")
st.title("📡 FusionSolar - Scanner Rotte API Gateway")

API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

# Elenco di tutte le rotte storiche e correnti usate da Huawei APIG per elencare gli impianti
TEST_PATHS = [
    "/rest/openapi/pvms/v1/getStationList",
    "/rest/openapi/pvms/v1/stationList",
    "/rest/openapi/pvms/v1/getDevList",
    "/rest/openapi/pvms/v1/getPlantList",
    "/rest/openapi/pvms/v1/getStationRealKpi",
    "/rest/openapi/pvms/v2/getStationList",
    "/thirdparty/station/list",
    "/thirdparty/getStationList",
    "/thirdparty/pvms/v1/getStationList",
    "/rest/pvms/v1/openapi/getStationList",
    "/rest/pvms/v1/getStationList",
    "/openapi/pvms/v1/getStationList",
    "/pvms/v1/getStationList",
    "/getStationList"
]

if st.button("🚀 Avvia Scansione Rotte APIG", type="primary"):
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "clientType": "0"
    })

    # 1. LOGIN
    st.subheader("1. Verifica Login")
    login_url = f"{BASE_DOMAIN}/rest/openapi/pvms/v1/login"
    
    try:
        res_login = session.post(login_url, json={"username": API_USER, "password": API_PASS}, timeout=12)
        st.write(f"**Status Code Login:** `{res_login.status_code}`")
        
        headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
        token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

        if not token:
            st.error("❌ Token non trovato. Impossibile proseguire con la scansione.")
            st.stop()

        st.success(f"🔑 Login OK. Token: `{token[:15]}...`")

        session.headers.update({
            "accessSession": token,
            "xsrf-token": token,
            "XSRF-TOKEN": token,
            "X-SRT": token
        })

    except Exception as e:
        st.error(f"Errore connessione Login: {e}")
        st.stop()

    # 2. SCANSIONE ROTTE
    st.subheader("2. Esito Scansione Endpoint APIG")
    
    results = []
    working_data = None
    working_path = None

    progress_bar = st.progress(0)
    
    for idx, path in enumerate(TEST_PATHS):
        full_url = f"{BASE_DOMAIN}{path}"
        try:
            res = session.post(full_url, json={"pageNo": 1, "pageSize": 100}, timeout=8)
            status = res.status_code
            
            try:
                data = res.json()
                err_code = data.get("error_code", "OK" if status == 200 else "-")
                msg = data.get("error_msg") or data.get("message") or "Risposta JSON"
                
                if status == 200 and err_code != "APIG.0101":
                    working_data = data
                    working_path = path
            except Exception:
                err_code = "HTML/Text"
                msg = res.text[:80].replace("\n", " ")

            results.append({
                "Percorso Testato": path,
                "HTTP Status": status,
                "Error Code APIG": err_code,
                "Dettaglio": msg
            })
        except Exception as ex:
            results.append({
                "Percorso Testato": path,
                "HTTP Status": "TIMEOUT/ERR",
                "Error Code APIG": "-",
                "Dettaglio": str(ex)
            })
            
        progress_bar.progress((idx + 1) / len(TEST_PATHS))

    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)

    if working_path:
        st.balloons()
        st.success(f"🎯 **TROVATA ROTTA ATTIVA:** `{working_path}`")
        st.json(working_data)
    else:
        st.warning("⚠️ Tutte le rotte hanno restituito APIG.0101 o 404.")
