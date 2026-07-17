import os
import requests
from auth import get_fusionsolar_session

# Configurazione credenziali da variabili d'ambiente di GitHub
USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    try:
        # 1. Recuperiamo la sessione valida e il token dopo aver superato i blocchi
        cookies, xsrf_token = get_fusionsolar_session(USERNAME, PASSWORD)
        
        # 2. Prepariamo gli header corretti per fare le richieste API
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json;charset=UTF-8",
            "X-XSRF-TOKEN": xsrf_token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        print("\n[*] Richiesta della lista degli impianti e controllo allarmi...")
        
        # Endpoint per ottenere la lista degli impianti (stazioni)
        url_stations = f"{FUSIONSOLAR_HOST}/rest/pvms/v1/station/station-list"
        
        # Corpo della richiesta (chiediamo i dettagli base inclusi gli allarmi)
        payload = {
            "pageNo": 1,
            "pageSize": 100,
            "sortName": "stationName",
            "sortOrder": "asc"
        }

        response = requests.post(url_stations, json=payload, cookies=cookies, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # La lista reale si trova di solito dentro data['data']['list'] o data['list'] a seconda della versione API
            stations = data.get("data", {}).get("list", []) or data.get("list", [])
            
            if not stations:
                print("[*] Nessun impianto trovato associato a questo account.")
                return

            print("\n" + "="*60)
            print("                 REPORT STATO IMPIANTI")
            print("="*60)

            # 3. Ciclo su ogni impianto per estrarre Nome e Stato Allarmi
            for station in stations:
                nome_impianto = station.get("stationName", "Impianto Sconosciuto")
                
                # Huawei di solito restituisce i contatori degli allarmi divisi per gravità:
                # faultRealTimeAlarmCount (critici), o simili allarmi attivi.
                allarmi_critici = station.get("faultRealTimeAlarmCount", 0)
                allarmi_gravi = station.get("seriousAlarmCount", 0) or station.get("seriousRealTimeAlarmCount", 0)
                allarmi_lievi = station.get("commonAlarmCount", 0) or station.get("subHealthRealTimeAlarmCount", 0)
                
                totale_allarmi = allarmi_critici + allarmi_gravi + allarmi_lievi

                # Generazione del messaggio richiesto
                if totale_allarmi > 0:
                    # Costruiamo il dettaglio degli allarmi attivi
                    dettaglio = []
                    if allarmi_critici > 0: dettaglio.append(f"{allarmi_critici} Critici")
                    if allarmi_gravi > 0: dettaglio.append(f"{allarmi_gravi} Gravi")
                    if allarmi_lievi > 0: dettaglio.append(f"{allarmi_lievi} Minori/Avvisi")
                    
                    stato_allarme = f"🚨 ATTIVO ({', '.join(dettaglio)})"
                else:
                    stato_allarme = "✅ nessun allarme"

                # Stampa del report pulito richiesto
                print(f"🔹 Impianto: {nome_impianto}")
                print(f"   Stato:    {stato_allarme}")
                print("-" * 40)
                
            print("="*60)
            print("[+] Report completato con successo!")

        else:
            print(f"[-] Impossibile recuperare i dati dell'impianto. Status code: {response.status_code}")
            print(f"[-] Risposta: {response.text}")

    except Exception as e:
        print(f"[-] Errore critico durante l'esecuzione del report: {e}")

if __name__ == "__main__":
    main()
