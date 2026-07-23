import os
import json
import logging
import requests

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------------------------------------------------------
# CONFIGURAZIONE ED ENDPOINT
# ---------------------------------------------------------------------------
BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdData"

# Legge le credenziali dalle variabili d'ambiente (GitHub Secrets)
# Se non trovate, usa i valori di fallback inseriti sotto
API_USER = os.getenv("FUSIONSOLAR_API_USER", "Monitoragg_api")
API_PASS = os.getenv("FUSIONSOLAR_API_KEY", "TestAPI2026")  # Imposta la tua password


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
                # Il token risiede nell'header 'xsrf-token' o all'interno del campo 'data'
                self.xsrf_token = response.headers.get("xsrf-token") or data.get("data")
                self.session.headers.update({"xsrf-token": self.xsrf_token})
                logging.info("Login effettuato con successo!")
                return True
            else:
                fail_code = data.get("failCode")
                message = data.get("message")
                logging.error(f"Login fallito [Codice {fail_code}]: {message}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Errore durante la richiesta di login: {e}")
            return False

    def get_station_list(self) -> list:
        """Recupera la lista di tutti gli impianti associati all'account."""
        if not self.xsrf_token:
            logging.error("Impossibile recuperare gli impianti: token mancante. Effettuare prima il login.")
            return []

        url = f"{self.base_url}/getStationList"
        logging.info("Recupero elenco impianti...")

        try:
            response = self.session.post(url, json={}, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                stations = data.get("data", [])
                logging.info(f"Trovati {len(stations)} impianti.")
                return stations
            else:
                logging.error(f"Errore nel recupero impianti: {data.get('failCode')}")
                return []

        except requests.exceptions.RequestException as e:
            logging.error(f"Errore durante la chiamata getStationList: {e}")
            return []

    def get_real_time_kpi(self, station_codes: list) -> dict:
        """
        Recupera i dati in tempo reale per una lista di stationCodes (max 100 per chiamata).
        
        :param station_codes: Lista di stringhe con i codici impianti (es. ["NE=182980048"])
        """
        if not self.xsrf_token:
            return {}

        url = f"{self.base_url}/getStationRealKpi"
        payload = {
            "stationCodes": ",".join(station_codes)
        }

        try:
            response = self.session.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                return data.get("data", [])
            else:
                logging.error(f"Errore recupero KPI: {data.get('failCode')}")
                return {}

        except requests.exceptions.RequestException as e:
            logging.error(f"Errore richiesta KPI real-time: {e}")
            return {}


# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
def main():
    api = FusionSolarAPI(
        base_url=BASE_URL,
        username=API_USER,
        password=API_PASS
    )

    # 1. Login
    if not api.login():
        logging.error("Procedura interrotta a causa del fallimento del login.")
        return

    # 2. Ottieni la lista degli impianti
    stations = api.get_station_list()
    
    if not stations:
        logging.warning("Nessun impianto trovato o errore nella chiamata.")
        return

    # 3. Salva la lista impianti su un file JSON locale
    output_file = "impianti_fusionsolar.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=4, ensure_ascii=False)
    
    logging.info(f"Elenco impianti salvato con successo in '{output_file}'.")

    # 4. Esempio: Estrarre i dati in tempo reale per i primi 10 impianti
    station_codes = [s["stationCode"] for s in stations[:10] if "stationCode" in s]
    if station_codes:
        logging.info(f"Richiesta dati Real-Time KPI per {len(station_codes)} impianti...")
        realtime_data = api.get_real_time_kpi(station_codes)
        
        # Stampa a video o salva i dati
        print("\n--- DATI IN TEMPO REALE (Esempio primi impianti) ---")
        print(json.dumps(realtime_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
