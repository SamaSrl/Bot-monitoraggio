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
        if not self.xsrf_token or not station_codes:
            return {}

        url = f"{self.base_url}/getKpiStationDay"
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


def estrai_dati_impianto(station):
    """Estrae nome, capacità reale (kWp) e coordinate geografiche precise."""
    nome = station.get("stationName", "N/D")
    
    # Capacità da Huawei o fallback mirato sul nome
    cap = 0.0
    try:
        cap = float(station.get("capacity") or station.get("capacityKwp") or 0)
    except:
        cap = 0.0

    # Tabella di riscontro taglie kWp se Huawei restituisce 0
    if cap <= 0:
        nome_lower = nome.lower()
        if "ponte rosso" in nome_lower: cap = 200.0
        elif "piaget" in nome_lower: cap = 100.0
        elif "dignano" in nome_lower: cap = 150.0
        elif "maniago" in nome_lower: cap = 150.0
        elif "moretto" in nome_lower: cap = 50.0
        elif "capannone" in nome_lower: cap = 100.0
        elif "rivignano" in nome_lower: cap = 200.0
        else: cap = 100.0

    # Ricerca coordinate geolocalizzate mirate sul comune
    lat, lon = 45.95, 13.03
    comune = "Rivignano" # Default zona
    nome_lower = nome.lower()
    
    if "ponte rosso" in nome_lower: comune = "San Giorgio di Nogaro"
    elif "piaget" in nome_lower or "maniago" in nome_lower: comune = "Maniago"
    elif "dignano" in nome_lower: comune = "Dignano"
    elif "moretto" in nome_lower: comune = "Codroipo"
    elif "capannone" in nome_lower: comune = "Rivignano"
    elif "rivignano" in nome_lower: comune = "Rivignano"

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={comune}&count=1&language=it&format=json"
        resp = requests.get(geo_url, timeout=4)
        if resp.status_code == 200:
            res = resp.json().get("results")
            if res:
                lat, lon = res[0].get("latitude"), res[0].get("longitude")
    except:
        pass

    return nome, cap, lat, lon


def get_irraggiamento_ieri(lat, lon) -> float:
    """Restituisce il valore pulito dell'irraggiamento solare di ieri (kWh/m^2)."""
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
        logging.warning(f"Errore meteo irraggiamento: {e}")

    return 0.0


class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 13)
        self.cell(0, 8, "Report Stato Impianti & Meteo FusionSolar", border=0, ln=True, align="C")
        self.set_font("Arial", "I", 8)
        self.cell(0, 5, "Produzione Reale di Ieri, Potenza Impianto e Irraggiamento", border=0, ln=True, align="C")
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

    # Intestazione Tabella (A4 larghezza utile ~190mm)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(55, 8, "Nome Impianto", border=1)
    pdf.cell(25, 8, "Potenza (kWp)", border=1, align="C")
    pdf.cell(25, 8, "Reale (kWh)", border=1, align="C")
    pdf.cell(25, 8, "Irrag. (kWh/m2)", border=1, align="C")
    pdf.cell(60, 8, "Stato / Errori", border=1, ln=True, align="C")

    for st in stations:
        station_code = st.get("stationCode", "")
        nome_raw, capacity_kwp, lat, lon = estrai_dati_impianto(st)
        nome = pulisci_testo(nome_raw)[:32]
        
        # Produzione Reale di Ieri
        prod_reale_val = kpi_map.get(station_code, 0.0)
        prod_reale_str = f"{prod_reale_val:,.2f}".replace(",", " ")

        # Irraggiamento Solare
        irraggiamento_val = get_irraggiamento_ieri(lat, lon)
        irraggiamento_str = f"{irraggiamento_val:,.2f}".replace(",", " ") if irraggiamento_val > 0 else "N/D"

        # Capacità formattata
        cap_str = f"{capacity_kwp:,.1f}".replace(",", " ")

        # Stato ed Errori
        if station_code in alarms_map and alarms_map[station_code]:
            stato_errore = pulisci_testo(alarms_map[station_code])[:30]
            ha_errore = True
        else:
            stato_errore = "OK"
            ha_errore = False

        pdf.set_font("Arial", size=8)
        pdf.cell(55, 7, nome, border=1)
        pdf.cell(25, 7, cap_str, border=1, align="C")
        pdf.cell(25, 7, prod_reale_str, border=1, align="C")
        pdf.cell(25, 7, irraggiamento_str, border=1, align="C")
        
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
