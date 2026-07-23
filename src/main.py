import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")
BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdstation/v1.0"

def main():
    if not API_USER or not API_KEY:
        print("[-] Errore: Credenziali FUSIONSOLAR_API_USER o FUSIONSOLAR_API_KEY non trovate.")
        return

    print("[*] Avvio estrazione dati impianti FusionSolar...")
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    })

    report_data = {
        "status": "error",
        "stations": [],
        "errors": []
    }

    try:
        # --- 1. LOGIN API ---
        print("[*] Autenticazione in corso...")
        login_res = session.post(f"{BASE_URL}/login", json={
            "systemCode": API_USER,
            "secretKey": API_KEY
        }, timeout=30)
        
        print(f"[*] Codice Risposta HTTP: {login_res.status_code}")

        try:
            login_json = login_res.json()
        except Exception:
            login_json = {"raw_response": login_res.text[:500]}
            print(f"[-] Risposta non JSON dal server: {login_res.text[:200]}")

        xsrf_token = login_res.headers.get("XSRF-TOKEN")
        if xsrf_token:
            session.headers.update({"XSRF-TOKEN": xsrf_token})

        if isinstance(login_json, dict) and (login_json.get("failCode") == 0 or login_json.get("success") is True):
            print("[+] Login API effettuato con successo!")
            report_data["status"] = "success"

            # --- 2. RECUPERO LISTA IMPIANTI ---
            print("[*] Richiesta lista impianti...")
            stations_res = session.post(f"{BASE_URL}/station/list", json={"pageNo": 1}, timeout=30)
            
            try:
                stations_json = stations_res.json()
                report_data["stations"] = stations_json.get("data", [])
                print(f"[+] Trovati {len(report_data['stations'])} impianti.")
            except Exception:
                report_data["errors"].append({"step": "get_stations", "response": stations_res.text[:500]})

            # --- 3. LOGOUT ---
            session.post(f"{BASE_URL}/logout", timeout=10)
            print("[*] Sessione API chiusa.")
        else:
            print(f"[-] Dettagli Errore Login: {login_json}")
            report_data["errors"].append({"step": "login", "details": login_json})

    except Exception as e:
        print(f"[-] Eccezione durante l'esecuzione: {e}")
        report_data["errors"].append({"step": "exception", "message": str(e)})

    # --- 4. SALVATAGGIO FILE JSON ---
    output_filename = "report_impianti.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"[+] File '{output_filename}' generato con successo!")

if __name__ == "__main__":
    main()
