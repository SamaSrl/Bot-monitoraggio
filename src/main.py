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
                logging.info("Login effettuato con successo!")
                return True
            else:
                logging.error(f"Login fallito: {data.get('message')}")
                return False
        except Exception as e:
            logging.error(f"Errore connessione login: {e}")
            return False

    def get_station_list(self) -> list:
        if not self.xsrf_token:
            return []
        
        url = f"{self.base_url}/getStationList"
        try:
            response = self.session.post(url, json={}, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if data.get("success") else []
        except Exception as e:
            logging.error(f"Errore recupero impianti: {e}")
            return []


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Report Impianti FusionSolar", ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def genera_pdf_impianti(stations, filename="report_impianti.pdf"):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Intestazione Tabella
    pdf.set_font("Arial", "B", 10)
    pdf.cell(80, 8, "Nome Impianto", border=1)
    pdf.cell(50, 8, "Codice Impianto", border=1)
    pdf.cell(60, 8, "Capacità (kWp)", border=1, ln=True)

    pdf.set_font("Arial", size=9)
    
    # Contenuto Tabella
    for st in stations:
        nome = str(st.get("stationName", "N/D"))[:35]  # Tronca nomi troppo lunghi
        codice = str(st.get("stationCode", "N/D"))
        capacita = str(round(float(st.get("capacity", 0)), 2))

        pdf.cell(80, 7, nome, border=1)
        pdf.cell(50, 7, codice, border=1)
        pdf.cell(60, 7, capacita, border=1, ln=True)

    pdf.output(filename)
    logging.info(f"PDF generato con successo: '{filename}'")


def main():
    api = FusionSolarAPI(BASE_URL, API_USER, API_PASS)

    if not api.login():
        return

    stations = api.get_station_list()
    if not stations:
        logging.warning("Nessun impianto trovato.")
        return

    # Genera il report PDF
    genera_pdf_impianti(stations, "report_impianti.pdf")


if __name__ == "__main__":
    main()
