import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright per simulare il login e catturare i cookie di sessione
    e il token XSRF necessari per le chiamate successive.
    """
    print("[*] Avvio del browser headless...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000) # Attesa precauzionale per il rendering completo

            # 1. Gestione Banner dei Cookie (La "X" in fondo a destra)
            try:
                cookie_close_button = page.locator("span.cookie-close, .cookie-policy-close, i.cookie-close, svg.cookie-close, [class*='cookie'] .x, [class*='cookie'] button").or_(page.get_by_text("×")).first
                if cookie_close_button.is_visible(timeout=3000):
                    print("[*] Rilevato banner dei cookie. Chiusura in corso...")
                    cookie_close_button.click()
                    page.wait_for_timeout(1000)
            except Exception:
                print("[*] Nessun banner cookie rilevato o impossibile chiuderlo (procedo comunque).")

            print("[*] Inserimento credenziali...")
            
            # 2. Individuazione e compilazione robusta del campo Username
            # Usiamo il testo del placeholder "Username/Email" visibile nello screenshot
            username_field = page.get_by_placeholder("Username/Email").or_(page.locator("input[type='text']")).first
            username_field.wait_for(state="visible", timeout=10000)
            username_field.click() # Clicca per dare il focus
            username_field.fill(username)

            # 3. Individuazione e compilazione robusta del campo Password
            password_field = page.get_by_placeholder("Password").or_(page.locator("input[type='password']")).first
            password_field.click()
            password_field.fill(password)
            
            print("[*] Clic sul pulsante di Login...")
            # Clicchiamo sul vistoso bottone blu "Log In"
            login_button = page.get_by_role("button", name="Log In").or_(page.locator("button:has-text('Log In')")).or_(page.locator(".login-btn")).first
            login_button.click()
            
            # Aspettiamo che il browser carichi la pagina principale post-login
            print("[*] Attesa reindirizzamento alla dashboard...")
            page.wait_for_url("**/index.html**", timeout=25000)
            print("[+] Login completato con successo!")

            # Estraiamo i cookie salvati nel browser
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Estraiamo l'XSRF-TOKEN
            xsrf_token = ""
            for cookie in cookies:
                if cookie['name'] == 'XSRF-TOKEN':
                    xsrf_token = cookie['value']
                    break

            browser.close()
            return session_cookies, xsrf_token

        except Exception as e:
            print(f"[-] Errore durante la sessione del browser: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Nuovo screenshot di errore salvato come 'error_screenshot.png'")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e