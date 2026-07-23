import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Host OpenAPI / Northbound ufficiale per la regione EU5
BASE_HOST = "https://eu5.fusionsolar.huawei.com"

def write_github_summary(content):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def main():
    if not API_USER or not API_KEY:
        write_github_summary("### ❌ Errore: Credenziali non trovate nei Secrets!\n")
        print("[-] Errore: FUSIONSOLAR_API_USER o FUSIONSOLAR_API_KEY non definiti.", flush=True)
        return

    print(f"[*] Connecting to FusionSolar API: {BASE_HOST}...", flush=True)
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    endpoint = f"{BASE_HOST}/thirdstation/v1.0/login"
    
    # Per gli utenti Northbound il payload standard è userName + systemCode
    payload = {
        "userName": API_USER,
        "systemCode": API_KEY
    }

    try:
        print(f"[*] Tentativo di login per l'utente '{API_USER}'...", flush=True)
        res = session.post(endpoint, json=payload, timeout=10)
        status = res.status_code
        print(f"[*] Risposta HTTP: {status}", flush=True)

        if status == 200:
            data = res.json()
            print(f"[*] Body Risposta: {data}", flush=True)

            fail_code = data.get("failCode")
            
            if fail_code == 0 or data.get("success") is True:
                xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                if xsrf:
                    session.headers.update({"XSRF-TOKEN": xsrf})

                summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"
                summary += "### 🟢 Login Riuscito!\n\n"

                # Recupero lista impianti
                print("[*] Richiesta lista impianti...", flush=True)
                st_res = session.post(f"{BASE_HOST}/thirdstation/v1.0/station/list", json={"pageNo": 1}, timeout=10)
                st_json = st_res.json()
                stations = st_json.get("data", [])

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
                    summary += "_Nessun impianto associato a questo utente API (verifica le selezioni nel portale)._\n"

                # Logout pulito
                session.post(f"{BASE_HOST}/thirdstation/v1.0/logout", timeout=5)
                write_github_summary(summary)
            else:
                summary = f"### 🔴 Errore Login API (failCode: {fail_code})\n\nDettagli: `{data}`\n"
                write_github_summary(summary)
        else:
            write_github_summary(f"### 🔴 Errore HTTP {status} dal server Huawei\n")

    except Exception as e:
        print(f"❌ Errore durante la connessione: {e}", flush=True)
        write_github_summary(f"### ❌ Errore Connessione: `{e}`\n")

if __name__ == "__main__":
    main()
