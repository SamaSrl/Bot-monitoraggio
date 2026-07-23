import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Host corretto identificato dal tuo login web
BASE_HOST = "https://uni004eu5.fusionsolar.huawei.com"

def write_github_summary(content):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def main():
    if not API_USER or not API_KEY:
        write_github_summary("### ❌ Errore: Credenziali non trovate nei Secrets!\n")
        print("[-] Errore: FUSIONSOLAR_API_USER o FUSIONSOLAR_API_KEY non definiti.")
        return

    print(f"[*] Avvio verifica API FusionSolar su: {BASE_HOST}...")
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    # Rotte possibili per la login (OpenAPI v1 vs Legacy Thirdstation)
    login_endpoints = [
        f"{BASE_HOST}/thirdstation/v1.0/login",
        f"{BASE_HOST}/rest/openapi/pvms/v1/login"
    ]

    # Formati payload usati da Huawei per le credenziali API
    payloads = [
        {"userName": API_USER, "systemCode": API_KEY},
        {"systemCode": API_USER, "secretKey": API_KEY},
        {"userName": API_USER, "value": API_KEY}
    ]

    success_endpoint = None
    error_logs = []

    # Scansione combinazioni Endpoint / Payload
    for endpoint in login_endpoints:
        if success_endpoint:
            break

        print(f"[*] Prova endpoint: {endpoint}")
        
        for p_idx, payload in enumerate(payloads):
            try:
                res = session.post(endpoint, json=payload, timeout=15)
                status = res.status_code

                if status == 200:
                    try:
                        data = res.json()
                        fail_code = data.get("failCode")
                        code = data.get("code")
                        
                        # Verifica successo (failCode == 0 oppure success == True oppure code == '0')
                        if fail_code == 0 or code == "0" or data.get("success") is True:
                            success_endpoint = endpoint
                            
                            # Estrazione token XSRF se presente nei cookie o negli header
                            xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                            if xsrf:
                                session.headers.update({"XSRF-TOKEN": xsrf})
                                
                            print(f"[+] LOGIN RIUSCITO! Endpoint attivo: {endpoint}")
                            break
                        else:
                            error_logs.append(f"`{endpoint}` (Payload {p_idx+1}): Risposta API `{data}`")
                    except Exception:
                        error_logs.append(f"`{endpoint}`: Risposta non JSON (Pagina HTML/404)")
                else:
                    error_logs.append(f"`{endpoint}`: Errore HTTP {status}")

            except Exception as e:
                error_logs.append(f"`{endpoint}`: Errore di connessione ({e})")

    # Costruzione del Report GitHub
    summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"

    if success_endpoint:
        summary += f"### 🟢 Connessione Riuscita!\n"
        summary += f"* **Endpoint Attivo:** `{success_endpoint}`\n\n"

        # Determinazione della rotta per la lista impianti
        if "/thirdstation/" in success_endpoint:
            stations_url = f"{BASE_HOST}/thirdstation/v1.0/station/list"
            logout_url = f"{BASE_HOST}/thirdstation/v1.0/logout"
        else:
            stations_url = f"{BASE_HOST}/rest/openapi/pvms/v1/station/list"
            logout_url = f"{BASE_HOST}/rest/openapi/pvms/v1/logout"

        # Recupero Impianti
        try:
            st_res = session.post(stations_url, json={"pageNo": 1}, timeout=15)
            st_json = st_res.json()
            
            # Estrazione lista in base al formato di risposta
            stations = st_json.get("data", [])
            if isinstance(stations, dict):
                stations = stations.get("list", [])

            summary += f"### 📊 Impianti Trovati ({len(stations)})\n\n"
            if stations:
                summary += "| Nome Impianto | Codice Impianto | Capacità (kWp) |\n"
                summary += "| :--- | :--- | :--- |\n"
                for s in stations:
                    name = s.get("stationName", "N/D")
                    code = s.get("stationCode", "N/D")
                    cap = s.get("capacity", "N/D")
                    summary += f"| **{name}** | `{code}` | {cap} kWp |\n"
            else:
                summary += "_Nessun impianto associato a questo utente API o risposta vuota._\n"
            
            # Chiusura sessione
            session.post(logout_url, timeout=5)

        except Exception as ex:
            summary += f"⚠️ Errore nel recupero della lista impianti: `{ex}`\n"
    else:
        summary += "### 🔴 Impossibile effettuare il login\n\n"
        summary += "**Dettagli dei tentativi falliti:**\n"
        for log in error_logs:
            summary += f"* {log}\n"
        
        summary += "\n---\n"
        summary += "💡 **Consigli per la verifica:**\n"
        summary += "1. Verifica se nelle credenziali `FUSIONSOLAR_API_USER` stai inserendo il Nome Utente OpenAPI creato dalla dashboard.\n"
        summary += "2. Verifica se in `FUSIONSOLAR_API_KEY` è presente il codice/password OpenAPI (System Code / Secret Key).\n"

    write_github_summary(summary)

if __name__ == "__main__":
    main()
