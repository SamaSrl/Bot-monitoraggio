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
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle")
            page.wait_for_timeout(5000) # Forziamo 5 secondi interi per assicurarci che gli script di Huawei siano pronti

            print("[*] Inserimento credenziali con metodo hardware...")
            
            # Selettore specifico per il campo Username di FusionSolar
            user_selector = "input[type='text'], .username-input input, input[placeholder*='User']"
            page.wait_for_selector(user_selector, timeout=15000)
            
            # Forziamo il focus e l'inserimento simulando la tastiera fisica
            page.focus(user_selector)
            page.click(user_selector)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(username, delay=100) # Digita lentamente come un umano

            # Selettore specifico per il campo Password di FusionSolar
            pass_selector = "input[type='password'], .password-input input, input[placeholder*='Pass']"
            page.focus(pass_selector)
            page.click(pass_selector)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(password, delay=100)
            
            print("[*] Invio del modulo di Login...")
            # Premiamo INVIO direttamente dalla tastiera per evitare di mancare il bottone blu
            page.keyboard.press("Enter")
            
            # Se l'invio con Enter non bastasse, fa anche il click di backup sul bottone
            page.wait_for_timeout(2000)
            try:
                page.locator("button[type='submit'], .login-btn, #login-submit, button:has-text('Log In')").first.click(timeout=3000)
            except Exception:
                pass # Se ha già fatto il redirect con Enter, questo fallirà ma andiamo avanti

            # Aspettiamo il caricamento della pagina principale post-login
            print("[*] Attesa reindirizzamento alla dashboard...")
            page.wait_for_url("**/index.html**", timeout=30000)
            print("[+] Login completato con successo!")

            # Estraiamo i cookie e il token
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
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
                print("[*] Nuovo screenshot di errore salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e