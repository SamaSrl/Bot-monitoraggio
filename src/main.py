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
            logging.error(f"Errore login: {e}")
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
            logging.error(f"Errore getStationList: {e}")
        return []

    def get_yesterday_kpi(self, station_codes: list) -> dict:
        """
        Interroga i KPI storici giornalieri di Huawei impostando esplicitamente
        il timestamp alla mezzanotte del giorno precedente per evitare dati parziali odierni.
        """
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getKpiStationDay"
        
        # Calcoliamo la mezzanotte esatta di ieri nel formato timestamp millisecondi locale/UTC accettato da Huawei
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
                    
                    # Chiavi standard Huawei per l'energia giornaliera consolidata
                    val = (
                        data_dict.get("day_power") 
                        or data_dict.get("product_power") 
                        or data_dict.get("inverter_power") 
                        or 0.0
                    )

                    try:
                        power_float = float(val)
                    except (ValueError, TypeError):
                        power_float = 0.0

                    if code:
                        kpi_map[code] = power_float
        except Exception as e:
            logging.error(f"Errore recupero KPI ieri: {e}")

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


def ottieni_coordinate(nome_impianto: str):
    """Ricava le coordinate geografiche dal nome dell'impianto tramite Open-Meteo Geocoding."""
    lat, lon = 45.95, 13.03 # Default Friuli
    parole = [p for p in nome_impianto.replace("-", " ").split() if p.lower() not in ["omnia", "immobiliare", "capannone", "nuovo", "scuola", "ponte", "rosso"]]
    for parola in parole:
        if len(parola) >= 3:
            try:
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={parola}&count=1&language=it&format=json"
                resp = requests.get(geo_url, timeout=4)
                if resp.status_code == 200:
                    res = resp.json().get("results")
                    if res:
                        lat, lon = res[0].get("latitude"), res[0].get("longitude")
                        break
            except:
                pass
    return lat, lon


def get_irraggiamento_ieri(lat, lon) -> float:
    """Restituisce solo il valore pulito dell'irraggiamento solare di ieri (kWh/m^2)."""
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
                # Conversione secca da MJ/m^2 a kWh/m^2 (1 kWh = 3.6 MJ)
                return round(rad_mj / 3.6, 2)
    except Exception as e:
        logging.warning(f"Errore meteo irraggiamento: {e}")

    return 0.0


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, "Report Stato Impianti & Meteo FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 8)
        self.cell(0, 5, "Produzione Reale di Ieri vs Irraggiamento Solare", border=0, ln=True, align="C")
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
    pdf = PDFReport()
    pdf.add_page()

    pdf.set_font("Arial", "B", 8)
    pdf.cell(70, 8, "Nome Impianto", border=1)
    pdf.cell(30, 8, "Reale (kWh)", border=1, align="C")
    pdf.cell(30, 8, "Irrag. (kWh/m2)", border=1, align="C")
    pdf.cell(60, 8, "Stato / Errori", border=1, ln=True, align="C")

    for st in stations:
        station_code = st.get("stationCode", "")
        nome_raw = st.get("stationName", "N/D")
        nome = pulisci_testo(nome_raw)[:38]
        
        lat, lon = ottieni_coordinate(nome_raw)

        # Produzione Reale di Ieri
        prod_reale_val = kpi_map.get(station_code, 0.0)
        prod_reale_str = f"{prod_reale_val:,.2f}".replace(",", " ")

        # Solo valore irraggiamento solare puro
        irraggiamento_val = get_irraggiamento_ieri(lat, lon)
        irraggiamento_str = f"{irraggiamento_val:,.2f}".replace(",", " ") if irraggiamento_val > 0 else "N/D"

        # Stato ed Errori
        if station_code in alarms_map and alarms_map[station_code]:
            stato_errore = pulisci_testo(alarms_map[station_code])[:32]
            ha_errore = True
        else:
            stato_errore = "OK"
            ha_errore = False

        pdf.set_font("Arial", size=8)
        pdf.cell(70, 7, nome, border=1)
        pdf.cell(30, 7, prod_reale_str, border=1, align="C")
        pdf.cell(30, 7, irraggiamento_str, border=1, align="C")
        
        if ha_errore:
            pdf.set_font("Arial", "B", 8)
            pdf.cell(60, 7, stato_errore, border=1, ln=True)
        else:
            pdf.set_font("Arial", size=8)
            pdf.cell(60, 7, stato_errore, border=1, ln=True, align="C")

    pdf.output(filename)


def main():
    api = FusionSolarAPI(BASE_URL, API_USER, API_PASS)
    if not api.login():
        return

    stations = api.get_station_list()
    if not stations:
        return

    all_codes = [s["stationCode"] for s in stations if "stationCode" in s]
    kpi_map, alarms_map = {}, {}
    
    for i in range(0, len(all_codes), 20):
        chunk = all_codes[i:i+20]
        kpi_map.update(api.get_yesterday_kpi(chunk))
        alarms_map.update(api.get_active_alarms(chunk))

    genera_pdf_impianti(stations, kpi_map, alarms_map, "report_impianti.pdf")


if __name__ == "__main__":
    main()
