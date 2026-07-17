import os
import json
from datetime import datetime
from auth import get_fusionsolar_session
from alarms import fetch_alarms

def main():
    # 1. Recupero credenziali dai Secrets impostati su GitHub
    user = os.getenv("FUSIONSOLAR_USER")
    password = os.getenv("FUSIONSOLAR_PASSWORD")
    
    if not user or not password:
        print("[-] Errore: Credenziali mancanti nei Secrets di GitHub!")
        return

    # 2. Flusso di estrazione dati
    try:
        # Login ed estrazione token
        cookies, token = get_fusionsolar_session(user, password)
        
        # Estrazione allarmi attivi
        allarmi = fetch_alarms(cookies, token)
        
        # 3. Creazione della struttura dati per la Web App
        report_data = {
            "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stato_generale": "Attenzione" if len(allarmi) > 0 else "OK",
            "allarmi_attivi": []
        }
        
        # Pulizia e formattazione allarmi per renderli leggeri sul JSON
        for alarm in allarmi:
            report_data["allarmi_attivi"].append({
                "nome_allarme": alarm.get("alarmName", "Allarme Sconosciuto"),
                "livello": alarm.get("severity", "Informativo"),
                "data_rilevazione": alarm.get("raiseTime", "N/D"),
                "impianto": alarm.get("stationName", "N/D")
            })
            
        # 4. Creazione cartella di output e salvataggio del file JSON
        os.makedirs("web_app/data", exist_ok=True)
        with open("web_app/data/dashboard.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=4, ensure_ascii=False)
            
        print("[+] Dati esportati con successo in web_app/data/dashboard.json!")
        
    except Exception as e:
    print(f"[-] Errore critico durante l'esecuzione: {e}")
    try:
        page.screenshot(path="error_screenshot.png")
        print("[*] Screenshot di errore salvato come error_screenshot.png")
    except Exception as screenshot_error:
        print(f"[-] Impossibile salvare lo screenshot: {screenshot_error}")
    raise e