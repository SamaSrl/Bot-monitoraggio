import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Il tuo server nativo identificato dal portal web
BASE_HOST = "https://uni004eu5.fusionsolar.huawei.com"

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

    print(f"[*] Connessione a FusionSolar OpenAPI su: {BASE_HOST}...", flush=True)
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    # Endpoint OpenAPI recente
    login_url = f"{BASE_HOST}/rest/openapi/pvms/v1/login"
    
    # Payload standard Huawei OpenAPI
    payload = {
        "userName": API_USER,
        "systemCode": API_KEY
    }

    try:
        print(f"[*] Tentativo di login per utente '{API_USER}'...", flush=True)
        res = session.post(login_url, json=payload, timeout=12)
        status = res.status_code
        print(f"[*] Risposta HTTP dal server: {status}", flush=True)

        if status == 200:
            data = res.json()
            print(f"[*] Dati ricevuti: {data}", flush=True)

            fail_code = data.get("failCode")
            code = str(data.get("code", ""))

            # Huawei OpenAPI restituisce code "0" o failCode 0 quando il login ha successo
            if fail_code == 0 or code == "0" or data.get("success") is True:
                # Recupero Token
                xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                if xsrf:
                    session.headers.update({"XSRF-TOKEN": xsrf})

                summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"
                summary += "### 🟢 Login Riuscito!\n\n"

                # Recupero Impianti
                print("[*] Richiesta lista impianti...", flush=True)
                list_url = f"{BASE_HOST}/rest/openapi/pvms/v1/station/list"
                st_res = session.post(list_url, json={"pageNo": 1}, timeout=12)
                st_json = st_res.json()
                
                stations = st_json.get("data", [])
                if isinstance(stations, dict):
                    stations = stations.get("list", [])

                summary += f"### 📊 Impianti Trovati ({len(stations)})\n\n"
                if stations:
                    summary += "| Nome Impianto | Codice Impianto | Capacità (kWp) |\n"
                    summary += "| :--- | :--- | :--- |\n"
                    for s in stations:
                        name = s.get("stationName", "N/D")
                        code_st = s.get("stationCode", "N/D")
                        cap = s.get("capacity", "N/D")
                        summary += f"| **{name}** | `{code_st}` | {cap} kWp |\n"
                else:
                    summary += "_Nessun impianto associato a questo utente API._\n"

                # Logout
                session.post(f"{BASE_HOST}/rest/openapi/pvms/v1/logout", timeout=5)
                write_github_summary(summary)
            else:
                summary = f"### 🔴 Login Rifiutato dall'API Huawei\n\n"
                summary += f"* **Codice Risposta:** `{code or fail_code}`\n"
                summary += f"* **Messaggio:** `{data}`\n"
                write_github_summary(summary)
        else:
            write_github_summary(f"### 🔴 Errore HTTP {status} dal server Huawei\n")

    except Exception as e:
        print(f"❌ Errore durante la connessione: {e}", flush=True)
        write_github_summary(f"### ❌ Errore Connessione: `{e}`\n")

if __name__ == "__main__":
    main()
