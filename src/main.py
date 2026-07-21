import os
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    print("[*] Avvio Bot Monitoraggio FusionSolar...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9"
        )
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            # --- STEP 1: INSERIMENTO USERNAME VIA COORDINATE / TASTIERA ---
            print("[*] Inserimento Username...")
            
            # Clicchiamo al centro del box dello username (X: 400, Y: 315 alla risoluzione 1920x1080)
            page.mouse.click(400, 315)
            page.wait_for_timeout(500)
            
            # Puliamo e scriviamo
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(USERNAME, delay=40)
            page.wait_for_timeout(500)

            # --- STEP 2: INSERIMENTO PASSWORD VIA TAB / COORDINATE ---
            print("[*] Inserimento Password...")
            
            # Clicchiamo al centro del box della password (X: 580, Y: 315)
            page.mouse.click(580, 315)
            page.wait_for_timeout(500)
            
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(PASSWORD, delay=40)
            page.wait_for_timeout(500)

            # --- STEP 3: CLICK ACCEDI ---
            print("[*] Invio credenziali...")
            
            # Salviamo prima uno screenshot di controllo per vedere se i dati sono comparsi
            page.screenshot(path="pre_login_check.png")
            
            # Clicchiamo sul pulsante azzurro 'Accedi' (X: 715, Y: 315)
            page.mouse.click(715, 315)
            page.keyboard.press("Enter")
            
            print("[*] Attesa risposta dal server...")
            page.wait_for_timeout(10000)

            # --- STEP 4: SCREENSHOT RISULTATO LOGIN ---
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo!")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante il processo: {e}")
            page.screenshot(path="dashboard_check.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
