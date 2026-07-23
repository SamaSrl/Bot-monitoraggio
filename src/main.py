import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Host identificato dal tuo login web
BASE_HOST = "https://uni004eu5.fusionsolar.huawei.com"

# In base alla versione attiva sul tuo account, il percorso di login varia:
ENDPOINTS_TO_TEST = [
    f"{BASE_HOST}/thirdstation/v1.0/login",
    f"{BASE_HOST}/rest/openapi/pvms/v1/login"
]
def write_github_summary(content):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def main():
    if not API_USER or not API_KEY:
        write_github_summary("### ❌ Errore: Credenziali non trovate nei Secrets!")
        return

    print("[*] Avvio Scansione Endpoint API Huawei FusionSolar...")
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    })

    success_host = None
    stations_found = []
    error_logs = []

    # Prova ciascun server con entrambi i formati di payload
    for host in API_HOSTS:
        print(f"[*] Test host: {host}")
        
        # Formato Payload Standard vs Formato Alternativo
        payloads = [
            {"systemCode": API_USER, "secretKey": API_KEY},
            {"userName": API_USER, "value": API_KEY}
        ]

        for p_idx, payload in enumerate(payloads):
            try:
                res = session.post(f"{host}/login", json=payload, timeout=12)
                status = res.status_code

                if status == 200:
                    try:
                        data = res.json()
                        fail_code = data.get("failCode")
                        
                        if fail_code == 0 or data.get("success") is True:
                            success_host = host
                            xsrf = res.headers.get("XSRF-TOKEN")
                            if xsrf:
                                session.headers.update({"XSRF-TOKEN": xsrf})
                            print(f"[+] LOGIN RIUSCITO SU {host}!")
                            break
                        else:
                            error_logs.append(f"`{host}` (Payload {p_idx+1}): Risposta API `{data}`")
                    except Exception:
                        error_logs.append(f"`{host}`: Risposta non JSON (Pagina HTML/404)")
                else:
                    error_logs.append(f"`{host}`: Errore HTTP {status}")

            except Exception as e:
                error_logs.append(f"`{host}`: Errore connessione ({e})")

        if success_host:
            break

    # Costruzione del report visuale per GitHub
    summary = "## ☀️ Report Diagnostico API FusionSolar\n\n"

    if success_host:
        summary += f"### 🟢 Connessione Riuscita!\n"
        summary += f"* **Server Attivo:** `{success_host}`\n\n"

        # Recupero Impianti
        try:
            st_res = session.post(f"{success_host}/station/list", json={"pageNo": 1}, timeout=15)
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
                summary += "_Nessun impianto associato a questo utente API._\n"
            
            session.post(f"{success_host}/logout", timeout=5)

        except Exception as ex:
            summary += f"⚠️ Errore nel recupero della lista impianti: `{ex}`\n"
    else:
        summary += "### 🔴 Nessun Endpoint ha Accettato la Connessione\n\n"
        summary += "**Dettagli dei tentativi falliti:**\n"
        for log in error_logs:
            summary += f"* {log}\n"
        
        summary += "\n---\n"
        summary += "💡 **Cosa verificare sul portale FusionSolar:**\n"
        summary += "1. Assicurati che l'utente creato sia di tipo **Northbound API** (non l'utente del portale web).\n"
        summary += "2. Verifica che nell'interfaccia FusionSolar, alla voce *Company Management* -> *OpenAPI*, l'utente sia nello stato **Enable** e legato al tuo impianto.\n"

    write_github_summary(summary)

if __name__ == "__main__":
    main()
