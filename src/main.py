import os
import json
import logging
import requests
from fpdf import FPDF

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Endpoint FusionSolar Northbound API
BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdData"

# Recupero credenziali dalle variabili d'ambiente (GitHub Secrets o locale)
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


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Report Impianti FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 9)
        self.cell(0, 5, "Estrazione automatica via OpenAPI Northbound", border=0, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def genera_pdf_impianti(stations, filename="report_impianti.pdf"):
    """Genera e formatta il report PDF con la lista degli impianti."""
    pdf = PDFReport()
    pdf.add_page()

    # Intestazione Tabella
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 8, "Nome Impianto", border=1)
    pdf.cell(55, 8, "Codice Stazione", border=1)
    pdf.cell(45, 8, "Capacita' (kWp)", border=1, ln=True)

    # Contenuto Tabella
    pdf.set_font("Arial", size=8)
    for st in stations:
        # Pulisce e tronca il nome per non sforare la cella
        nome = str(st.get("stationName", "N/D")).encode('latin-1', 'replace').decode('latin-1')[:45]
        codice = str(st.get("stationCode", "N/D"))
        capacita = str(round(float(st.get("capacity", 0)), 2))

        pdf.cell(90, 6, nome, border=1)
        pdf.cell(55, 6, codice, border=1)
        pdf.cell(45, 6, capacita, border=1, ln=True)

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
        logging.error("Procedura interrotta.")
        return

    # 2. Ottieni la lista impianti
    stations = api.get_station_list()
    if not stations:
        logging.warning("Nessun impianto trovato.")
        return

    # 3. Genera il report PDF
    genera_pdf_impianti(stations, "report_impianti.pdf")


if __name__ == "__main__":
    main()
