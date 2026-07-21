import os
import json
from playwright.sync_api import sync_playwright

COOKIES_JSON = os.environ.get("FUSIONSOLAR_COOKIES")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    print("[*] Avvio Bot Monitoraggio via Session Cookies...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT"
        )
        
        # Iniezione Cookie di Sessione se presenti
        if COOKIES_JSON:
            try:
                cookies = json.loads(COOKIES_JSON)
                context.add_cookies(cookies)
                print("[+] Cookie di sessione caricati con successo!")
            except Exception as e:
                print(f"[!] Errore nel caricamento dei cookie JSON: {e}")
        else:
            print("[!] ATTENZIONE: Secret FUSIONSOLAR_COOKIES non trovato nei segreti!")

        page = context.new_page()

        try:
            print(f"[*] Apertura diretta Dashboard FusionSolar...")
            # Navighiamo direttamente alla homepage interna / dashboard
            page.goto(f"{FUSIONSOLAR_HOST}/pvmswebsite/assets/build/index.html#/kpi", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(8000)

            # Se veniamo reindirizzati alla login, proviamo l'URL radice
            if "login" in page.url:
                print("[!] Reindirizzato su login, tento caricamento radice...")
                page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle")
                page.wait_for_timeout(8000)

            print(f"[+] URL Attuale: {page.url}")

            # Salvataggio dello screenshot della Dashboard
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo!")

        except Exception as e:
            print(f"[-] Errore nell'accesso via cookie: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
