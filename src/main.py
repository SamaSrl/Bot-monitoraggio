import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Domini dedicati alle API di Huawei (evitano il blocco 503 dell'interfaccia web)
HOSTS_TO_TEST = [
    "https://intl.fusionsolar.huawei.com",
    "https://region010.fusionsolar.huawei.com",
    "https://eu5.fusionsolar.huawei.com"
]

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

    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    success_data = None
    error_logs = []

    for host in HOSTS_TO_TEST:
        print(f"\n[*] Prova Host API: {host}", flush=True)
        
        # Testiamo sia l'endpoint Northbound v1 che OpenAPI PVMS v1
        endpoints = [
            (f"{host}/thirdstation/v1.0/login", {"userName": API_USER, "systemCode": API_KEY}),
            (f"{host}/rest/openapi/pvms/v1/login", {"userName": API_USER, "systemCode": API_KEY})
        ]

        for url, payload in endpoints:
            print(f"    └─ Calling {url}...", flush=True)
            try:
                res = session.post(url, json=payload, timeout=10)
                status = res.status_code
                print(f"       Status: {status}", flush=True)

                if status == 200:
                    data = res.json()
                    fail_code = data.get("failCode")
                    code = str(data.get("code", ""))

                    if fail_code == 0 or code == "0" or data.get("success") is True:
                        print(f"[+] SUCCESS! Connesso a {url}", flush=True)
                        success_data = (host, url, data)
                        
                        xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                        if xsrf:
                            session.headers.update({"XSRF-TOKEN": xsrf})
                        break
                    else:
                        error_logs.append(f"`{url}`: Risposta `{data}`")
                else:
                    error_logs.append(f"`{url}`: Errore HTTP {status}")

            except Exception as e:
                error_logs.append(f"`{url}`: {e}")

        if success_data:
            break

    # Generazione Report
    summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"

    if success_data:
        host, active_url, response = success_data
        summary += f"### 🟢 Connessione Riuscita!\n"
        summary += f"* **Host Attivo:** `{host}`\n"
        summary += f"* **Endpoint:** `{active_url}`\n\n"

        # Recupero lista impianti
        is_thirdstation = "/thirdstation/" in active_url
        list_url = f"{host}/thirdstation/v1.0/station/list" if is_thirdstation else f"{host}/rest/openapi/pvms/v1/station/list"
        logout_url = f"{host}/thirdstation/v1.0/logout" if is_thirdstation else f"{host}/rest/openapi/pvms/v1/logout"

        try:
            st_res = session.post(list_url, json={"pageNo": 1}, timeout=10)
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

            session.post(logout_url, timeout=5)
        except Exception as ex:
            summary += f"⚠️ Errore recupero impianti: `{ex}`\n"
    else:
        summary += "### 🔴 Nessun Endpoint ha Accettato la Connessione\n\n"
        for log in error_logs:
            summary += f"* {log}\n"

    write_github_summary(summary)

if __name__ == "__main__":
    main()
