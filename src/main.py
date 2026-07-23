import os
import json
import logging
import requests
from datetime import datetime, timedelta
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
        Recupera la produzione (kWh) del giorno precedente per gli impianti.
        Ritorna un dizionario: { stationCode: "123.45" }
        """
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getKpiStationDay"
        
        # Calcola il timestamp in millisecondi per l'inizio della giornata di ieri
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
        collect_time = int(yesterday_start.timestamp() * 1000)

        payload = {
            "stationCodes": ",".join(station_codes),
            "collectTime": collect_time
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
                    # 'inverter_power' o 'day_power' indica la produzione giornaliera in kWh
                    power = data_dict.get("inverter_power") or data_dict.get("day_power") or 0.0
                    if code:
                        kpi_map[code] = str(round(float(power), 2))
            else:
                logging.warning(f"Chiamata KPI Day completata con esito: {data.get('failCode')}")

        except Exception as e:
            logging.error(f"Errore nel recupero dati di produzione: {e}")

        return kpi_map

    def get_active_alarms(self, station_codes: list) -> dict:
        """
        Recupera gli allarmi attivi/non gestiti per la lista di impianti fornita.
        Ritorna un dizionario: { stationCode: "Nome Errore / Descrizione" }
        """
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
            "status": 1  # 1 = allarmi attivi
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


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Report Stato Impianti FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 9)
        self.cell(0, 5, "Estrazione automatica via OpenAPI Northbound", border=0, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def pulisci_testo(testo: str) -> str:
    """Rimuove caratteri speciali non supportati dal font Latin-1 di FPDF."""
    if not testo:
        return ""
    return str(testo).encode('latin-1', 'replace').decode('latin-1')


def genera_pdf_impianti(stations, kpi_map, alarms_map, filename="report_impianti.pdf"):
    """Genera e formatta il report PDF con Nome, Produzione Ieri e Stato/Errori."""
    pdf = PDFReport()
    pdf.add_page()

    # Intestazione Tabella (A4 = 190 mm larghezza utile)
    # 90 mm Nome + 35 mm Produzione + 65 mm Stato/Errori
    pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 8, "Nome Impianto", border=1)
    pdf.cell(35, 8, "Prod. Ieri (kWh)", border=1, align="C")
    pdf.cell(65, 8, "Stato / Errori", border=1, ln=True, align="C")

    # Contenuto Tabella
    for st in stations:
        station_code = st.get("stationCode", "")
        nome = pulisci_testo(st.get("stationName", "N/D"))[:45]
        
        # Produzione Ieri
        prod_ieri = kpi_map.get(station_code, "0.0")
        
        # Determina lo stato dell'errore
        if station_code in alarms_map and alarms_map[station_code]:
            stato_errore = pulisci_testo(alarms_map[station_code])[:35]
            ha_errore = True
        else:
            stato_errore = "OK"
            ha_errore = False

        # Stampa riga
        pdf.set_font("Arial", size=8)
        pdf.cell(90, 7, nome, border=1)
        pdf.cell(35, 7, prod_ieri, border=1, align="C")
        
        # Se c'è un errore lo mettiamo in grassetto
        if ha_errore:
            pdf.set_font("Arial", "B", 8)
            pdf.cell(65, 7, stato_errore, border=1, ln=True)
        else:
            pdf.set_font("Arial", size=8)
            pdf.cell(65, 7, stato_errore, border=1, ln=True, align="C")

    pdf.output(filename)
    logging.info(f"PDF generato con successo: '{filename}'")


def main():
    api = FusionSolarAPI(
        base_url=BASE_URL,
        username=API_USER,
        password=API_PASS
    )

    # 1. Login
    if not api.login():
        logging.error("Procedura interrotta: login fallito.")
        return

    # 2. Ottieni la lista impianti
    stations = api.get_station_list()
    if not stations:
        logging.warning("Nessun impianto trovato.")
        return

    all_station_codes = [s["stationCode"] for s in stations if "stationCode" in s]
    
    kpi_map = {}
    alarms_map = {}
    
    # 3. Recupera Produzione Ieri e Allarmi a blocchi da 50 impianti
    chunk_size = 50
    for i in range(0, len(all_station_codes), chunk_size):
        chunk = all_station_codes[i:i + chunk_size]
        logging.info(f"Elaborazione blocco impianti {i+1}-{i+len(chunk)}...")
        
        # Dati produzione ieri
        chunk_kpi = api.get_yesterday_kpi(chunk)
        kpi_map.update(chunk_kpi)
        
        # Allarmi
        chunk_alarms = api.get_active_alarms(chunk)
        alarms_map.update(chunk_alarms)

    # 4. Genera il report PDF completo
    genera_pdf_impianti(stations, kpi_map, alarms_map, "report_impianti.pdf")


if __name__ == "__main__":
    main()
