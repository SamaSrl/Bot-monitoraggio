import streamlit as st
import requests

st.set_page_config(page_title="FusionSolar - Northbound API", page_icon="📡", layout="wide")
st.title("📡 FusionSolar - Northbound API (thirdData)")

# --- Credenziali: NON hardcodare in produzione, usa st.secrets ---
# Esempio: crea .streamlit/secrets.toml con:
# API_USER = "il_tuo_username_northbound"
# API_SYSTEM_CODE = "il_tuo_systemCode"
API_USER = st.secrets.get("API_USER", "")
API_SYSTEM_CODE = st.secrets.get("API_SYSTEM_CODE", "")

BASE_DOMAIN = "https://eu5.fusionsolar.huawei.com"

if not API_USER or not API_SYSTEM_CODE:
    st.warning("Imposta API_USER e API_SYSTEM_CODE in .streamlit/secrets.toml prima di procedere.")

if st.button("🚀 Login e recupero lista impianti", type="primary"):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 1. LOGIN — endpoint corretto: /thirdData/login
    # Body: userName + systemCode (NON username/password)
    st.subheader("1. Login")
    login_url = f"{BASE_DOMAIN}/thirdData/login"

    try:
        res_login = session.post(
            login_url,
            json={"userName": API_USER, "systemCode": API_SYSTEM_CODE},
            timeout=12,
        )
        st.write(f"**Status Code Login:** `{res_login.status_code}`")

        try:
            login_data = res_login.json()
            st.json(login_data)
        except Exception:
            login_data = {}
            st.text(res_login.text[:500])

        # Il token arriva come header xsrf-token E/O cookie XSRF-TOKEN
        headers_lower = {k.lower(): v for k, v in res_login.headers.items()}
        token = headers_lower.get("xsrf-token") or session.cookies.get("XSRF-TOKEN")

        if not token:
            st.error(
                "❌ Token non trovato. Possibili cause: credenziali errate, "
                "account Northbound disabilitato, oppure una sessione già attiva "
                "altrove (l'API consente 1 sola sessione per account)."
            )
            st.stop()

        st.success(f"🔑 Login OK. Token: `{token[:15]}...`")

        # Per le chiamate successive serve SOLO l'header xsrf-token
        session.headers.update({"xsrf-token": token})

    except Exception as e:
        st.error(f"Errore connessione Login: {e}")
        st.stop()

    # 2. LISTA IMPIANTI — endpoint corretto: /thirdData/getStationList
    st.subheader("2. Lista impianti")
    station_url = f"{BASE_DOMAIN}/thirdData/getStationList"

    try:
        res = session.post(station_url, json={}, timeout=12)
        st.write(f"**Status Code:** `{res.status_code}`")

        try:
            data = res.json()
        except Exception:
            st.error("Risposta non JSON:")
            st.text(res.text[:500])
            st.stop()

        if data.get("success") is True or data.get("failCode") in (None, 0):
            st.balloons()
            st.success("🎯 Lista impianti recuperata correttamente")
            st.json(data)
        else:
            st.warning(f"⚠️ Chiamata fallita. Dettaglio risposta:")
            st.json(data)
            st.info(
                "Codici di errore comuni:\n"
                "- **305**: sessione/utente bloccato, troppe richieste ravvicinate\n"
                "- **407**: token/xsrf-token non valido o scaduto\n"
                "- **010**: parametri mancanti/non validi\n"
                "- **020**: nessun permesso sull'impianto/account"
            )
    except Exception as ex:
        st.error(f"Errore nella richiesta: {ex}")
