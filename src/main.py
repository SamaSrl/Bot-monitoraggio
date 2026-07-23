import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Host ed Endpoint CORRETTI identificati dal test
BASE_HOST = "https://eu5.fusionsolar.huawei.com"
LOGIN_URL = f"{BASE_HOST}/rest/openapi/pvms/v1/login"

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

    # Pulisce eventuali spazi presi per errore nei Secrets di GitHub
    user_clean = API_USER.strip()
    key_clean = API_KEY.strip()

    print(f"[*] Connessione a FusionSolar OpenAPI EU5 per l'utente '{user_clean}'...", flush=True)
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    # Formati di payload possibili per la nuova OpenAPI PVMS
    payloads = [
        {"userName": user_clean, "systemCode": key_clean},
        {"userName": user_clean, "value": key_clean},
        {"systemCode": user_clean, "secretKey": key_clean}
    ]

    success = False
    last_response = None

    for idx, payload in enumerate(payloads):
        print(f"[*] Prova Formato Payload #{idx + 1}...", flush=True)
        try:
            res = session.post(LOGIN_URL, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                last_response = data
                print(f"    └─ Risposta Server: {data}", flush=True)

                fail_code = data.get("failCode")
                code = str(data.get("code", ""))

                if fail_code == 0 or code == "0" or data.get("success") is True:
                    success = True
                    xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                    if xsrf:
                        session.headers.update({"XSRF-TOKEN": xsrf})
                    print("[+] LOGIN RIUSCITO CON SUCCESSO!", flush=True)
                    break
        except Exception as e:
            print(f"    └─ Errore chiamata: {e}", flush=True)

    # Generazione Report per GitHub
    summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"

    if success:
        summary += "### 🟢 Login Riuscito Su EU5 OpenAPI!\n\n"

        # Richiesta lista impianti
        try:
            list_url = f"{BASE_HOST}/rest/openapi/pvms/v1/station/list"
            print("[*] Recupero lista impianti...", flush=True)
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

        except Exception as ex:
            summary += f"⚠️ Errore nel recupero impianti: `{ex}`\n"
    else:
        summary += "### 🔴 Credenziali / Parametri non Accettati\n\n"
        summary += f"* **Endpoint:** `{LOGIN_URL}`\n"
        summary += f"* **Ultima Risposta API:** `{last_response}`\n\n"
        summary += "💡 **Verifica nei Secrets di GitHub:**\n"
        summary += "1. `FUSIONSOLAR_API_USER`: Inserisci esattamente il nome utente Northbound (es. `Monitoragg_api`).\n"
        summary += "2. `FUSIONSOLAR_API_KEY`: Inserisci la password associata a questo utente su FusionSolar (fai attenzione a maiuscole/minuscole e che non sia scaduta).\n"

    write_github_summary(summary)

if __name__ == "__main__":
    main()
