import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="FusionSolar - Accesso Diretto", page_icon="🔑", layout="wide")
st.title("🔑 Test Accesso Diretto & Diagnostic Server")

# Credenziali dirette da testare
API_USER = "Monitoragg_api"
API_PASS = "Casa150117!!"

# Testiamo il dominio primario e i domini di fallback Huawei
PRIMARY_DOMAIN = "https://eu5.fusionsolar.huawei.com"

if st.button("🚀 Esegui Connessione Diretta", type="primary"):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    st.subheader("1. FASE LOGIN")
    login_url = f"{PRIMARY_DOMAIN}/rest/openapi/pvms/v1/login"
    login_payload = {"username": API_USER, "password": API_PASS}

    try:
        res_login = session.post(login_url, json=login_payload, timeout=12)
        st.write(f"**Status Code Login:** `{res_login.status_code}`")
        
        login_json = res_login.json()
        st.json(login_json)

        # Estrazione token
        headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
        token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

        if not token:
            st.error("❌ Impossibile ottenere il token XSRF.")
            st.stop()

        st.success(f"🔑 Token ottenuto con successo: `{token[:15]}...`")

        # Impostazione Header Northbound ufficiali
        session.headers.update({
            "accessSession": token,
            "xsrf-token": token,
            "X-SRT": token
        })

        st.markdown("---")
        st.subheader("2. CHECK REGIONE SERVER (Host Redirection Check)")
        
        # Verifichiamo se l'account appartiene davvero a EU5 o se va reindirizzato
        host_url = f"{PRIMARY_DOMAIN}/rest/openapi/pvms/v1/getSystemServerHost"
        res_host = session.post(host_url, json={}, timeout=12)
        
        st.write(f"**Risposta Reindirizzamento Host:**")
        try:
            st.json(res_host.json())
        except Exception:
            st.text(res_host.text)

        st.markdown("---")
        st.subheader("3. RICHIESTA LISTA STAZIONI (`getStationList`)")

        # Invio con payload completo predefinito per la paginazione
        station_url = f"{PRIMARY_DOMAIN}/rest/openapi/pvms/v1/getStationList"
        station_payload = {"pageNo": 1, "pageSize": 100}

        res_stations = session.post(station_url, json=station_payload, timeout=12)
        st.write(f"**Status Code Stazioni:** `{res_stations.status_code}`")

        try:
            stations_json = res_stations.json()
            st.json(stations_json)

            if stations_json.get("success"):
                data = stations_json.get("data", {})
                list_data = data.get("list", []) if isinstance(data, dict) else data
                st.success(f"🎉 Trovati **{len(list_data)}** impianti!")
                st.dataframe(pd.DataFrame(list_data), use_container_width=True)

        except Exception as e:
            st.error(f"Errore nella lettura della risposta stazioni: {e}")
            st.code(res_stations.text, language="html")

    except Exception as e:
        st.error(f"Errore di connessione: {e}")
