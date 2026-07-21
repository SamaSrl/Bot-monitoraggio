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
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            # --- STEP 1: CHIUSURA BANNER COOKIE SE PRESENTE ---
            print("[*] Gestione banner cookie/overlay...")
            try:
                # Clicca sulla 'X' del banner cookie in basso se presente
                cookie_close = page.locator("text='X', .pv-cookie-close, button:has-text('Accetta')").first
                if cookie_close.is_visible():
                    cookie_close.click(force=True)
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # --- STEP 2: INSERIMENTO USERNAME TRAMITE TASTIERA ---
            print("[*] Inserimento Username via Tastiera...")
            user_input = page.locator("input[name='ssoCredentials.username'], input[placeholder*='utente']").first
            user_input.click(force=True)
            page.wait_for_timeout(300)
            # Puliamo eventuale testo esistente e scriviamo lo username
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(USERNAME, delay=30)
            page.wait_for_timeout(500)

            # --- STEP 3: INSERIMENTO PASSWORD TRAMITE TASTIERA ---
            print("[*] Inserimento Password via Tastiera...")
            pwd_input = page.locator("input[name='ssoCredentials.password'], input[type='password']").first
            pwd_input.click(force=True)
            page.wait_for_timeout(300)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(PASSWORD, delay=30)
            page.wait_for_timeout(500)

            # --- STEP 4: CLICK ACCEDI ---
            print("[*] Invio credenziali...")
            page.keyboard.press("Enter")
            
            # Per sicurezza clicchiamo anche sul pulsante azzurro se non è partito l'Enter
            page.wait_for_timeout(1000)
            login_btn = page.locator("button:has-text('Accedi'), span:has-text('Accedi')").first
            try:
                if login_btn.is_visible():
                    login_btn.click(force=True)
            except Exception:
                pass

            print("[*] Attesa risposta dal server...")
            page.wait_for_timeout(10000)

            # --- STEP 5: SCREENSHOT DI VERIFICA ---
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
