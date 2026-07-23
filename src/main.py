import os
import requests
import json

API_USER = os.environ.get("FUSIONSOLAR_API_USER")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY")

# Lista degli URL API da provare in sequenza
API_HOSTS = [
    "https://intl.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://eu5.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://region004.fusionsolar.huawei.com/thirdstation/v1.0"
]

def write_github_summary(content):
    """Scrive direttamente nella pagina di GitHub Actions senza scaricare file"""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def main():
    if not API_USER or not API_KEY:
        error_msg = "### ❌ Errore: Credenziali API non trovate nei Secrets!\n"
        print(error_msg)
        write_github_summary(error_msg)
        return

    print("[*] Avvio bot monitoraggio API FusionSolar...")
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    })

    login_success = False
    active_host = ""
    login_response_data = None

    # Prova gli host per trovare quello corretto
    for host in API_HOSTS:
        print(f"[*] Tentativo di login su: {host}/login ...")
        try:
            res = session.post(f"{host}/login", json={"systemCode": API_USER, "secretKey": API_KEY}, timeout=15)
            if res.status_code == 200:
                try:
                    data = res.json()
                    if data.get("failCode") == 0 or data.get("success") is True:
                        login_success = True
                        active_host = host
                        login_response_data = data
                        xsrf_token = res.headers.get("XSRF-TOKEN")
                        if xsrf_token:
                            session.headers.update({"XSRF-TOKEN": xsrf_token})
                        print(f"[+] Connesso con successo su {host}!")
                        break
                    else:
                        print(f"[!] Risposta login fallita su {host}: {data}")
                except Exception:
                    print(f"[-] Risposta non JSON da {host}")
        except Exception as e:
            print(f"[-] Errore di connessione a {host}: {e}")

    # Costruzione report per la schermata di GitHub
    summary_markdown = "## ☀️ Report Monitoraggio FusionSolar\n\n"

    if login_success:
        summary_markdown += f"**Stato Connessione:** 🟢 Connesso (`{active_host}`)\n\n"
        
        # Recupero lista impianti
        stations_res = session.post(f"{active_host}/station/list", json={"pageNo": 1}, timeout=15)
        try:
            st_data = stations_res.json()
            stations = st_data.get("data", [])
            summary_markdown += f"### 📊 Lista Impianti ({len(stations)})\n\n"
            
            if stations:
                summary_markdown += "| Nome Impianto | Codice | Capacità (kWp) | Stato |\n"
                summary_markdown += "| :--- | :--- | :--- | :--- |\n"
                for s in stations:
                    name = s.get("stationName", "N/D")
                    code = s.get("stationCode", "N/D")
                    cap = s.get("capacity", "N/D")
                    summary_markdown += f"| **{name}** | `{code}` | {cap} kWp | 🟢 Attivo |\n"
            else:
                summary_markdown += "_Nessun impianto associato a questo account API._\n"
        except Exception as e:
            summary_markdown += f"❌ Errore lettura impianti: {e}\n"

        session.post(f"{active_host}/logout", timeout=5)
    else:
        summary_markdown += "**Stato Connessione:** 🔴 Fallita (404 / Credenziali non valide)\n\n"
        summary_markdown += "> **Suggerimento:** Verifica di aver inserito l'Utente API e la Secret Key corretti generati per il protocollo Northbound OpenAPI.\n"

    # Scrittura nel sommario visuale di GitHub
    write_github_summary(summary_markdown)

if __name__ == "__main__":
    main()
