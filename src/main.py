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
        
        # Iniezione Cookie
        if COOKIES_JSON:
            try:
                cookies = json.loads(COOKIES_JSON)
                context.add_cookies(cookies)
                print("[+] Cookie caricati con successo!")
            except Exception as e:
                print(f"[!] Errore parsing cookie: {e}")
        else:
            print("[!] ATTENZIONE: Secret FUSIONSOLAR_COOKIES non trovato nei segreti!")

        page = context.new_page()

        try:
            print(f"[*] Navigazione sulla Home Page di FusionSolar...")
            # Carichiamo la root URL per permettere il reindirizzamento automatico della sessione
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(10000)

            print(f"[+] URL di atterraggio: {page.url}")

            # Salva screenshot del risultato
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato!")

        except Exception as e:
            print(f"[-] Errore nell'accesso: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
