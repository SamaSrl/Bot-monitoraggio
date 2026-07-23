import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

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

    user_clean = API_USER.strip()
    key_clean = API_KEY.strip()

    print(f"[*] Avvio autenticazione per utente Northbound: '{user_clean}'...", flush=True)
    
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    # Combinazioni di Host, Endpoint e Payload usati da Huawei per utenti Northbound
    tests = [
        # Opzione A: Host nativo uni004eu5 con OpenAPI PVMS
        {
            "url": "https://uni004eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1/login",
            "payload": {"userName": user_clean, "systemCode": key_clean},
            "type": "pvms"
        },
        # Opzione B: Host eu5 con formato Northbound Alternativo
        {
            "url": "https://eu5.fusionsolar.huawei.com/rest/openapi/pvms/v1/login",
            "payload": {"systemCode": user_clean, "secretKey": key_clean},
            "type": "pvms"
        },
        # Opzione C: Host uni004eu5 con formato Northbound Legacy
        {
            "url": "https://uni004eu5.fusionsolar.huawei.com/thirdstation/v1.0/login",
            "payload": {"userName": user_clean, "systemCode": key_clean},
            "type": "thirdstation"
        }
    ]

    success_test = None
    last_response = None

    for idx, test in enumerate(tests):
        print(f"[*] Prova Combinazione #{idx + 1}: {test['url']}...", flush=True)
        try:
            res = session.post(test["url"], json=test["payload"], timeout=12)
            print(f"    └─ HTTP Status: {res.status_code}", flush=True)
            
            if res.status_code == 200:
                data = res.json()
                last_response = data
                print(f"    └─ Risposta Server: {data}", flush=True)

                fail_code = data.get("failCode")
                code = str(data.get("code", ""))

                if fail_code == 0 or code == "0" or data.get("success") is True:
                    success_test = test
                    xsrf = res.headers.get("XSRF-TOKEN") or session.cookies.get("XSRF-TOKEN")
                    if xsrf:
                        session.headers.update({"XSRF-TOKEN": xsrf})
                    print("[+] LOGIN RIUSCITO!", flush=True)
                    break
        except Exception as e:
            print(f"    └─ Errore di connessione: {e}", flush=True)

    summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"

    if success_test:
        summary += "### 🟢 Login Riuscito con Successo!\n\n"
        summary += f"* **Endpoint Attivo:** `{success_test['url']}`\n\n"

        # Determinazione dell'URL per recuperare gli impianti
        if success_test["type"] == "thirdstation":
            host_base = success_test["url"].split("/thirdstation")[0]
            list_url = f"{host_base}/thirdstation/v1.0/station/list"
            logout_url = f"{host_base}/thirdstation/v1.0/logout"
        else:
            host_base = success_test["url"].split("/rest")[0]
            list_url = f"{host_base}/rest/openapi/pvms/v1/station/list"
            logout_url = f"{host_base}/rest/openapi/pvms/v1/logout"

        try:
            print("[*] Recupero lista impianti...", flush=True)
            st_res = session.post(list_url, json={"pageNo": 1}, timeout=15)
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
            summary += f"⚠️ Errore nel recupero impianti: `{ex}`\n"
    else:
        summary += "### 🔴 Impossibile effettuare il Login\n\n"
        summary += f"* **Ultimo Messaggio dal Server:** `{last_response}`\n\n"

    write_github_summary(summary)

if __name__ == "__main__":
    main()
