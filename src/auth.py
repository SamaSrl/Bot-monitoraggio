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

        print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
        page.goto(f"{FUSIONSOLAR_HOST}/")
        page.wait_for_load_state("networkidle")

        print("[*] Inserimento credenziali...")
        # Compila i campi di login (usa selettori generici e robusti)
        page.locator("input[type='text']").first.fill(username)
        page.locator("input[type='password']").fill(password)
        
        print("[*] Clic sul pulsante di Login...")
        page.locator("button[type='submit']").click()
        
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