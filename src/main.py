import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from fpdf import FPDF

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Endpoint FusionSolar Northbound API
BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdData"

# Credenziali dalle variabili d'ambiente (GitHub Secrets o valore locale di fallback)
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
        """Effettua l'autenticazione sull'endpoint /thirdData/login."""
        url = f"{self.base_url}/login"
        payload = {
            "userName": self.username,
            "systemCode": self.password
        }

        logging.info(f"Connessione in corso a FusionSolar per l'utente '{self.username}'...")

        try:
            response = self.session.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                self.xsrf_token = response.headers.get("xsrf-token") or data.get("data")
                self.session.headers.update({"xsrf-token": self.xsrf_token})
                logging.info("Login effettuato con successo!")
                return True
            else:
                logging.error(f"Login fallito: {data.get('message')}")
                return False

        except Exception as e:
            logging.error(f"Errore durante la connessione per il login: {e}")
            return False

    def get_station_list(self) -> list:
        """Recupera la lista di tutti gli impianti associati all'account."""
        if not self.xsrf_token:
            logging.error("Token non presente. Impossibile richiedere la lista impianti.")
            return []

        url = f"{self.base_url}/getStationList"
        logging.info("Recupero elenco impianti in corso...")

        try:
            response = self.session.post(url, json={}, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                stations = data.get("data", [])
                logging.info(f"Trovati {len(stations)} impianti.")
                return stations
            else:
                logging.error(f"Errore recupero impianti: {data.get('failCode')}")
                return []

        except Exception as e:
            logging.error(f"Errore durante la chiamata getStationList: {e}")
            return []

    def get_yesterday_kpi(self, station_codes: list) -> dict:
        """
        Recupera la produzione totale (kWh) del giorno precedente.
        Formatta collectTime calcolando il timestamp UTC di ieri alle 00:00:00.
        """
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getKpiStationDay"
        
        # Calcolo inizio giornata di ieri in UTC millisecondi
        now_utc = datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_midnight = datetime(yesterday_utc.year, yesterday_utc.month, yesterday_utc.day, 0, 0, 0, tzinfo=timezone.utc)
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
                kpi_list = data.get("data", [])
                for item in kpi_list:
                    code = item.get("stationCode")
                    data_dict = item.get("dataItemMap", {})
                    
                    # Estrazione e fallback tra le varie chiavi di produzione della risposta Huawei Northbound
                    val = None
                    for key in ["inverter_power", "product_power", "day_power", "theory_power", "use_power"]:
                        if key in data_dict and data_dict[key] is not None:
                            val = data_dict[key]
                            break

                    try:
                        power_float = float(val) if val is not None else 0.0
                    except (ValueError, TypeError):
                        power_float = 0.0

                    if code:
                        kpi_map[code] = power_float
            else:
                logging.warning(f"Chiamata KPI Day con codice esito: {data.get('failCode')}")

        except Exception as e:
            logging.error(f"Errore nel recupero dati di produzione: {e}")

        return kpi_map

    def get_active_alarms(self, station_codes: list) -> dict:
        """Recupera gli allarmi attivi per la lista di impianti."""
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
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                alarm_list = data.get("data", [])
                for alarm in alarm_list:
                    code = alarm.get("stationCode")
                    alarm_name = alarm.get("alarmName") or alarm.get("alarmNameEn") or "Errore Rilevato"
                    
                    if code:
                        if code in alarms_map:
                            alarms_map[code] += f", {alarm_name}"
                        else:
                            alarms_map[code] = alarm_name

        except Exception as e:
            logging.error(f"Errore nel recupero degli allarmi: {e}")

        return alarms_map


def ottieni_coordinate_da_nome(nome_impianto: str):
    """
    Se l'API Huawei non fornisce le coordinate lat/lon, cerca il comune dal nome dell'impianto
    usando la geocodifica gratuita di Open-Meteo.
    """
    if not nome_impianto:
        return None, None

    # Tenta di estrarre parole rilevanti escludendo prefissi come 'Omnia', 'Immobiliare', 'Capannone'
    parole = [p for p in nome_impianto.replace("-", " ").split() if p.lower() not in ["omnia", "immobiliare", "capannone", "nuovo", "scuola"]]
    
    for parola in parole:
        if len(parola) < 3:
            continue
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={parola}&count=1&language=it&format=json"
            resp = requests.get(geo_url, timeout=5)
            if resp.status_code == 200:
                results = resp.json().get("results")
                if results and len(results) > 0:
                    return results[0].get("latitude"), results[0].get("longitude")
        except Exception:
            pass
            
    # Coordinate di fallback nel caso nessun nome coincida (Friuli / Centro-Nord Italia default)
    return 45.95, 13.03


def calcola_produzione_attesa_meteo(lat, lon, capacity_kwp) -> float:
    """
    Calcola la produzione teorica attesa (kWh) in base alla radiazione solare reale di ieri.
    Usa l'API Open-Meteo Historical Weather.
    """
    if not lat or not lon:
        return 0.0

    # Se la capacità non è dichiarata dall'API Huawei, impostiamo un valore standard stimato
    cap = float(capacity_kwp) if capacity_kwp and float(capacity_kwp) > 0 else 500.0

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
                # Conversione da MJ/m^2 a kWh/m^2 (1 kWh = 3.6 MJ)
                irradiance_kwh_m2 = rad_mj / 3.6
                
                # Produzione Attesa: Cap (kWp) * Irraggiamento (kWh/m^2) * Performance Ratio (0.75)
                expected_kwh = cap * irradiance_kwh_m2 * 0.75
                return round(expected_kwh, 2)
    except Exception as e:
        logging.warning(f"Errore recupero meteo: {e}")

    return 0.0


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, "Report Stato Impianti & Meteo FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 8)
        self.cell(0, 5, "Confronto Produzione Reale vs Stima Meteo di Ieri", border=0, ln=True, align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def pulisci_testo(testo: str) -> str:
    if not testo:
        return ""
    return str(testo).encode('latin-1', 'replace').decode('latin-1')


def genera_pdf_impianti(stations, kpi_map, alarms_map, filename="report_impianti.pdf"):
    """Genera e formatta il report PDF con meteo e stato."""
    pdf = PDFReport()
    pdf.add_page()

    # Intestazione Tabella
    pdf.set_font("Arial", "B", 8)
    pdf.cell(70, 8, "Nome Impianto", border=1)
    pdf.cell(30, 8, "Reale (kWh)", border=1, align="C")
    pdf.cell(30, 8, "Attesa Meteo", border=1, align="C")
    pdf.cell(60, 8, "Stato / Errori", border=1, ln=True, align="C")

    for st in stations:
        station_code = st.get("stationCode", "")
        nome_raw = st.get("stationName", "N/D")
        nome = pulisci_testo(nome_raw)[:38]
        
        # Gestione lat/lon da Huawei o da Geocoding automatico
        lat = st.get("latitude") or st.get("lat")
        lon = st.get("longitude") or st.get("lon")
        
        if not lat or not lon:
            lat, lon = ottieni_coordinate_da_nome(nome_raw)

        capacity = st.get("capacity") or st.get("capacityKwp")

        # Produzione Reale
        prod_reale_val = kpi_map.get(station_code, 0.0)
        prod_reale_str = f"{prod_reale_val:,.2f}".replace(",", " ")

        # Produzione Attesa Meteo
        prod_attesa_val = calcola_produzione_attesa_meteo(lat, lon, capacity)
        prod_attesa_str = f"{prod_attesa_val:,.2f}".replace(",", " ") if prod_attesa_val > 0 else "N/D"

        # Stato Errori
        if station_code in alarms_map and alarms_map[station_code]:
            stato_errore = pulisci_testo(alarms_map[station_code])[:32]
            ha_errore = True
        else:
            stato_errore = "OK"
            ha_errore = False

        # Stampa riga PDF
        pdf.set_font("Arial", size=8)
        pdf.cell(70, 7, nome, border=1)
        pdf.cell(30, 7, prod_reale_str, border=1, align="C")
        pdf.cell(30, 7, prod_attesa_str, border=1, align="C")
        
        if ha_errore:
            pdf.set_font("Arial", "B", 8)
            pdf.cell(60, 7, stato_errore, border=1, ln=True)
        else:
            pdf.set_font("Arial", size=8)
            pdf.cell(60, 7, stato_errore, border=1, ln=True, align="C")

    pdf.output(filename)
    logging.info(f"PDF generato con successo: '{filename}'")


def main():
    api = FusionSolarAPI(
        base_url=BASE_URL,
        username=API_USER,
        password=API_PASS
    )

    if not api.login():
        logging.error("Procedura interrotta: login fallito.")
        return

    stations = api.get_station_list()
    if not stations:
        logging.warning("Nessun impianto trovato.")
        return

    all_station_codes = [s["stationCode"] for s in stations if "stationCode" in s]
    
    kpi_map = {}
    alarms_map = {}
    
    # Interroghiamo a blocchi di 20 impianti
    chunk_size = 20
    for i in range(0, len(all_station_codes), chunk_size):
        chunk = all_station_codes[i:i + chunk_size]
        logging.info(f"Elaborazione blocco {i+1}-{i+len(chunk)} di {len(all_station_codes)}...")
        
        chunk_kpi = api.get_yesterday_kpi(chunk)
        kpi_map.update(chunk_kpi)
        
        chunk_alarms = api.get_active_alarms(chunk)
        alarms_map.update(chunk_alarms)

    genera_pdf_impianti(stations, kpi_map, alarms_map, "report_impianti.pdf")


if __name__ == "__main__":
    main()
