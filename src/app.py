import os
import json
import logging
import requests
from datetime import datetime, timedelta
from fpdf import FPDF
import streamlit as st

st.set_page_config(
    page_title="FusionSolar Web App Manager", 
    page_icon="☀️", 
    layout="wide"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdData"
API_USER = os.getenv("FUSIONSOLAR_API_USER", "Monitoragg_api")
API_PASS = os.getenv("FUSIONSOLAR_API_KEY", "TestAPI2026")


class FusionSolarAPI:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.xsrf_token = None

    def login(self) -> bool:
        url = f"{self.base_url}/login"
        payload = {"userName": self.username, "systemCode": self.password}
        try:
            response = self.session.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                self.xsrf_token = response.headers.get("xsrf-token") or data.get("data")
                self.session.headers.update({"xsrf-token": self.xsrf_token})
                return True
        except Exception as e:
            st.error(f"Errore di login su Huawei FusionSolar: {e}")
        return False

    def get_station_list(self) -> list:
        url = f"{self.base_url}/getStationList"
        try:
            response = self.session.post(url, json={}, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                return data.get("data", [])
        except Exception as e:
            st.error(f"Errore caricamento lista impianti: {e}")
        return []

    def get_yesterday_kpi(self, station_codes: list) -> dict:
        """
        Estrae la produzione reale di ieri in modo pulito e consolidato.
        Usa il timestamp calcolato sulla mezzanotte esatta di ieri.
        """
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getKpiStationDay"
        
        # Definiamo la mezzanotte esatta di ieri
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_midnight = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
        collect_time_ms = int(yesterday_midnight.timestamp() * 1000)

        payload = {
            "stationCodes": ",".join(station_codes),
            "collectTime": collect_time_ms
        }

        kpi_map = {}
        try:
            response = self.session.post(url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                for item in data.get("data", []):
                    code = item.get("stationCode")
                    data_dict = item.get("dataItemMap", {})
                    
                    # Cerca prima il dato giornaliero specifico, poi gli accumulatori validi
                    val = (
                        data_dict.get("day_power") 
                        or data_dict.get("product_power") 
                        or data_dict.get("inverter_power") 
                        or 0.0
                    )
                    try:
                        val_float = float(val)
                        # Se per errore dovesse restituire i watt anziché i kWh o valori anomali
                        kpi_map[code] = val_float
                    except:
                        kpi_map[code] = 0.0
        except Exception as e:
            logging.error(f"Errore KPI: {e}")

        return kpi_map

    def get_active_alarms(self, station_codes: list) -> dict:
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getAlarmList"
        now = datetime.now()
        begin_time = int((now - timedelta(days=3)).timestamp() * 1000)
        end_time = int(now.timestamp() * 1000)
        payload = {
            "stationCodes": ",".join(station_codes),
            "beginTime": begin_time,
            "endTime": end_time,
            "status": 1
        }

        alarms_map = {}
        try:
            response = self.session.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    for alarm in data.get("data", []):
                        code = alarm.get("stationCode")
                        name = alarm.get("alarmName") or "Errore"
                        if code:
                            alarms_map[code] = alarms_map.get(code, "") + (", " if code in alarms_map else "") + name
        except Exception as e:
            logging.error(f"Errore allarmi: {e}")

        return alarms_map


def get_meteo_giornaliero(lat, lon) -> float:
    """Interroga Open-Meteo per l'irraggiamento solare di ieri (kWh/m^2)."""
    if not lat or not lon:
        return 0.0

    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": yesterday_str,
        "end_date": yesterday_str,
        "daily": "shortwave_radiation_sum",
        "timezone": "auto"
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            rad_mj = data.get("daily", {}).get("shortwave_radiation_sum", [0])[0]
            if rad_mj is not None:
                return round(rad_mj / 3.6, 2)
    except Exception as e:
        logging.warning(f"Errore meteo: {e}")

    return 0.0


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, "Report Stato Impianti & Meteo FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 8)
        self.cell(0, 5, "Dati Giornalieri Consolidati di Ieri", border=0, ln=True, align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def pulisci_testo(testo: str) -> str:
    if not testo:
        return ""
    return str(testo).encode('latin-1', 'replace').decode('latin-1')


def genera_pdf_report(risultati_finali, filename="report_impianti.pdf"):
    pdf = PDFReport()
    pdf.add_page()

    pdf.set_font("Arial", "B", 8)
    pdf.cell(50, 8, "Nome Impianto", border=1)
    pdf.cell(20, 8, "kWp", border=1, align="C")
    pdf.cell(22, 8, "Reale (kWh)", border=1, align="C")
    pdf.cell(25, 8, "Irrag. (kWh/m2)", border=1, align="C")
    pdf.cell(18, 8, "Tilt/Az", border=1, align="C")
    pdf.cell(55, 8, "Stato / Errori", border=1, ln=True, align="C")

    for r in risultati_finali:
        pdf.set_font("Arial", size=8)
        pdf.cell(50, 7, pulisci_testo(r["nome"])[:28], border=1)
        pdf.cell(20, 7, f"{r['potenza']:,.1f}", border=1, align="C")
        pdf.cell(22, 7, f"{r['reale']:,.2f}".replace(",", " "), border=1, align="C")
        pdf.cell(25, 7, f"{r['irraggiamento']:,.2f}".replace(",", " "), border=1, align="C")
        pdf.cell(18, 7, f"{r['tilt']}°/{r['azimut']}°", border=1, align="C")
        
        if r["ha_errore"]:
            pdf.set_font("Arial", "B", 8)
            pdf.cell(55, 7, pulisci_testo(r["errore"])[:28], border=1, ln=True)
        else:
            pdf.set_font("Arial", size=8)
            pdf.cell(55, 7, pulisci_testo(r["errore"]), border=1, ln=True, align="C")

    pdf.output(filename)
    return filename


# --- INTERFACCIA STREAMLIT ---
st.title("☀️ Gestione Impianti & Report FusionSolar")

api = FusionSolarAPI(BASE_URL, API_USER, API_PASS)

# Funzione per generare i valori predefiniti intelligenti
def crea_riga_impianto(s):
    nome = s.get("stationName", "N/D")
    code = s.get("stationCode", "")
    cap_default = float(s.get("capacity") or 100.0)
    lat_default, lon_default, tilt_default, azimut_default = 45.95, 13.03, 20.0, 180.0
    
    nome_l = nome.lower()
    if "ponte rosso" in nome_l: cap_default, lat_default, lon_default = 200.0, 45.81, 13.22
    elif "piaget" in nome_l or "maniago" in nome_l: cap_default, lat_default, lon_default = 100.0, 46.16, 12.70
    elif "dignano" in nome_l: cap_default, lat_default, lon_default = 150.0, 46.07, 12.94
    elif "moretto" in nome_l: cap_default, lat_default, lon_default = 50.0, 45.95, 13.03
    elif "rivignano" in nome_l or "capannone" in nome_l: cap_default, lat_default, lon_default = 200.0, 45.88, 13.12

    return {
        "stationCode": code,
        "Nome Impianto": nome,
        "Potenza (kWp)": cap_default,
        "Latitudine": lat_default,
        "Longitudine": lon_default,
        "Tilt (°)": tilt_default,
        "Azimut (°)": azimut_default
    }

# Inizializzazione sessione impianti
if "stations_data" not in st.session_state:
    with st.spinner("Connessione iniziale a FusionSolar..."):
        if api.login():
            raw_stations = api.get_station_list()
            st.session_state["stations_data"] = [crea_riga_impianto(s) for s in raw_stations]
        else:
            st.session_state["stations_data"] = []

# --- COLONNA DI CONTROLLO: TASTO AGGIUNGI IMPIANTI ---
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Sincronizza Nuovi Impianti", use_container_width=True):
        with st.spinner("Controllo nuovi impianti su Huawei..."):
            if api.login():
                raw_stations = api.get_station_list()
                codici_esistenti = [row["stationCode"] for row in st.session_state["stations_data"]]
                
                aggiunti = 0
                for s in raw_stations:
                    if s.get("stationCode") not in codici_esistenti:
                        st.session_state["stations_data"].append(crea_riga_impianto(s))
                        aggiunti += 1
                st.success(f"Sincronizzazione completata! Aggiunti {aggiunti} nuovi impianti (i vecchi dati modificati sono salvi).")
                st.rerun()

if st.session_state["stations_data"]:
    st.subheader("📋 Tabella Parametri Impianti")
    st.info("Puoi modificare liberamente le celle. Cliccando su 'Sincronizza Nuovi Impianti' eventuali tetti nuovi verranno aggiunti in fondo senza perdere le tue modifiche.")
    
    edited_df = st.data_editor(
        st.session_state["stations_data"],
        num_rows="fixed",
        use_container_width=True,
        key="editable_stations"
    )

    st.markdown("---")

    if st.button("🚀 RUN - Estrai Dati di Ieri e Genera Report", type="primary", use_container_width=True):
        with st.spinner("Estrazione dati reali di ieri da Huawei in corso..."):
            if not api.login():
                st.error("Errore di login durante l'estrazione.")
            else:
                codes = [row["stationCode"] for row in edited_df if row["stationCode"]]
                kpi_map = api.get_yesterday_kpi(codes)
                alarms_map = api.get_active_alarms(codes)

                risultati = []
                # Aggiorniamo lo stato in memoria con le modifiche fatte dall'utente nella tabella
                st.session_state["stations_data"] = edited_df

                for row in edited_df:
                    code = row["stationCode"]
                    nome = row["Nome Impianto"]
                    potenza = float(row["Potenza (kWp)"])
                    lat = float(row["Latitudine"])
                    lon = float(row["Longitudine"])
                    tilt = float(row["Tilt (°)"])
                    azimut = float(row["Azimut (°)"])

                    prod_reale = kpi_map.get(code, 0.0)
                    irraggiamento = get_meteo_giornaliero(lat, lon)
                    
                    errore = alarms_map.get(code, "OK")
                    ha_err = code in alarms_map and bool(alarms_map[code])

                    risultati.append({
                        "nome": nome,
                        "potenza": potenza,
                        "reale": prod_reale,
                        "irraggiamento": irraggiamento,
                        "tilt": tilt,
                        "azimut": azimut,
                        "errore": errore,
                        "ha_errore": ha_err
                    })

                pdf_path = genera_pdf_report(risultati)
                st.success("✅ Dati di ieri estratti con successo!")

                st.subheader("📊 Anteprima Risultati")
                st.dataframe(risultati, use_container_width=True)

                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Scarica Report PDF di Ieri",
                        data=pdf_file,
                        file_name=f"report_ieri_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
else:
    st.warning("Nessun impianto trovato. Controlla la connessione.")