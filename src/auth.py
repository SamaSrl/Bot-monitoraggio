import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito (cambialo se il tuo account è su un'altra regione)
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright per simulare il login e catturare i cookie di sessione
    e il token XSRF necessari per le chiamate successive.
    """
    print("[*] Avvio del browser headless...")
    
    with sync_playwright() as p:
        # Avviamo il browser in background (headless=True)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/")
            page.wait_for_load_state("networkidle")

            print("[*] Inserimento credenziali...")
            # Usa selettori multipli più specifici per FusionSolar (id username, classi comuni o input generico come fallback)
            # Aspetta fino a 10 secondi che il campo sia visibile prima di scattare l'errore
            try:
                page.wait_for_selector("input[type='text'], input[placeholder*='user'], input[placeholder*='User'], #username", timeout=10000)
            except Exception as select_timeout:
                print("[-] Campi di login non rilevati entro 10 secondi. Tento il salvataggio dello screenshot...")
                raise select_timeout

            # Compila le credenziali
            page.locator("input[type='text'], #username").first.fill(username)
            page.locator("input[type='password'], #password").first.fill(password)
            
            print("[*] Clic sul pulsante di Login...")
            page.locator("button[type='submit'], .login-btn, #login-submit").first.click()
            
            # Aspettiamo che il browser carichi la pagina principale post-login
            print("[*] Attesa reindirizzamento alla dashboard...")
            page.wait_for_url("**/index.html**", timeout=20000)
            print("[+] Login completato con successo!")

            # Estraiamo i cookie salvati nel browser
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Estraiamo l'XSRF-TOKEN indispensabile per fare le chiamate POST
            xsrf_token = ""
            for cookie in cookies:
                if cookie['name'] == 'XSRF-TOKEN':
                    xsrf_token = cookie['value']
                    break

            browser.close()
            return session_cookies, xsrf_token

        except Exception as e:
            # Cattura lo screenshot nel momento esatto del fallimento, prima che il browser venga chiuso
            print(f"[-] Errore durante la sessione del browser: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot di errore salvato con successo come 'error_screenshot.png'")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            # Chiudiamo comunque il browser per non lasciare processi appesi
            browser.close()
            raise e