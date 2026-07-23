import os
import requests
import json

# Recupero credenziali dai Secrets di GitHub
API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Endpoint Ufficiale OpenAPI per la regione EU5
BASE_HOST = "https://eu5.fusionsolar.huawei.com"
LOGIN_URL = f"{BASE_HOST}/rest/openapi/pvms/v1/login"
STATION_LIST_URL = f"{BASE_HOST}/rest/openapi/pvms/v1/station/list"
LOGOUT_URL = f"{BASE_HOST}/rest/openapi/pvms/v1/logout"

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

    # Pulizia automatica da eventuali spazi presi per errore nei secrets
    user_clean = API_USER.strip()
    key_clean = API_KEY.strip()

    print(f"[*] Avvio connessione a FusionSolar EU5 per utente: '{user_clean}'...", flush=True)
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    # Payload UFFICIALE Huawei OpenAPI Northbound
    payload = {
        "userName": user_clean,
        "systemCode": key_clean
    }

    try:
        res = session.post(LOGIN_URL, json=payload, timeout=15)
        print(f"[*] Risposta HTTP: {res.status_code}", flush=True)

        if res.status_code == 200:
            data = res.json()
            print(f"[*] Risposta JSON Server: {data}", flush=True)

            fail_code = data.get("failCode")
            code = str(data.get("code", ""))

            # Verifico se il login ha avuto successo
            if fail_code == 0 or code == "0" or data.get("success") is True:
                # Recupero Token di Sicurezza XSRF
                xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                if xsrf:
                    session.headers.update({"XSRF-TOKEN": xsrf})

                summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"
                summary += "### 🟢 Login Riuscito con Successo!\n\n"

                # Chiamata per recuperare gli impianti selezionati
                print("[*] Richiesta lista impianti in corso...", flush=True)
                st_res = session.post(STATION_LIST_URL, json={"pageNo": 1}, timeout=15)
                st_json = st_res.json()
                print(f"[*] Risposta Impianti: {st_json}", flush=True)

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

                # Logout pulito della sessione
                session.post(LOGOUT_URL, timeout=5)
                write_github_summary(summary)

            else:
                summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"
                summary += "### 🔴 Credenziali Rifiutate da Huawei\n\n"
                summary += f"* **Codice Errore Huawei:** `{fail_code or code}`\n"
                summary += f"* **Dettaglio:** `{data.get('message', data)}`\n\n"
                summary += "💡 **Cosa fare:**\n"
                summary += "1. Riapri la scheda dell'utente `Monitoragg_api` su FusionSolar.\n"
                summary += "2. Attiva lo switch **Cambia password**, inserisci una nuova password e premi **OK**.\n"
                summary += "3. Aggiorna il Secret `FUSIONSOLAR_API_KEY` su GitHub con la nuova password.\n"
                write_github_summary(summary)
        else:
            write_github_summary(f"### 🔴 Errore HTTP {res.status_code} dal server Huawei\n")

    except Exception as e:
        print(f"❌ Errore durante la chiamata: {e}", flush=True)
        write_github_summary(f"### ❌ Errore Connessione: `{e}`\n")

if __name__ == "__main__":
    main()
