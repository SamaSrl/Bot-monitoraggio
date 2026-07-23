import os
import requests
import json

# Credenziali API registrate nei Secret di GitHub
API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# URL API Northbound Huawei (Region Europe - EU5)
BASE_URL = "https://eu5.fusionsolar.huawei.com/thirdstation/v1.0"

def main():
    if not API_USER or not API_KEY:
        print("[-] Errore: Credenziali API (FUSIONSOLAR_API_USER / FUSIONSOLAR_API_KEY) mancanti nei Secrets di GitHub.")
        return

    print("[*] Avvio Bot Monitoraggio FusionSolar via API Northbound...")
    session = requests.Session()
    
    # Intestazioni standard per le chiamate REST
    session.headers.update({
        "Content-Type": "application/json"
    })

    # --- STEP 1: AUTENTICAZIONE API ---
    login_url = f"{BASE_URL}/login"
    payload = {
        "systemCode": API_USER,
        "secretKey": API_KEY
    }

    try:
        print(f"[*] Richiesta di Login API su {login_url}...")
        response = session.post(login_url, json=payload, timeout=30)
        res_data = response.json()

        if res_data.get("failCode") != 0 and not res_data.get("success", False):
            print(f"[-] Errore di autenticazione API: {res_data}")
            return

        # Estrazione del token CSRF dagli header se presente
        xsrf_token = response.headers.get("XSRF-TOKEN")
        if xsrf_token:
            session.headers.update({"XSRF-TOKEN": xsrf_token})

        print("[+] Autenticazione API riuscita!")

        # --- STEP 2: RECUPERO LISTA IMPIANTI (STATIONS) ---
        print("[*] Recupero lista degli impianti...")
        stations_url = f"{BASE_URL}/station/list"
        
        # Paginazione standard API Huawei
        stations_res = session.post(stations_url, json={"pageNo": 1}, timeout=30)
        stations_data = stations_res.json()

        print("\n=== RISULTATO DATI IMPIANTI ===")
        print(json.dumps(stations_data, indent=2, ensure_ascii=False))

        # --- STEP 3: LOGOUT (Buona norma per non consumare la quota di sessioni) ---
        logout_url = f"{BASE_URL}/logout"
        session.post(logout_url, timeout=10)
        print("\n[+] Sessione API chiusa correttamente.")

    except Exception as e:
        print(f"[-] Errore durante la chiamata API: {e}")

if __name__ == "__main__":
    main()
