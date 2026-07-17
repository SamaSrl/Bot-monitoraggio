import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright penetrando lo Shadow DOM con selettori nativi ultra-mirati.
    """
    print("[*] Avvio del browser con supporto Shadow DOM...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9",
            timezone_id="Europe/Rome"
        )
        
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            
            print("[*] Attesa stabilizzazione pagina...")
            page.wait_for_timeout(8000) # Attesa per assicurarci che l'interfaccia si sia montata completamente

            print("[*] Compilazione campi (rilevamento tramite Shadow DOM)...")
            
            # Questi selettori CSS penetrano nativamente qualsiasi livello di Shadow DOM in Playwright.
            # Cerchiamo gli elementi 'input' puri in base alla loro tipologia.
            user_input = page.locator("input[type='text']").first
            pass_input = page.locator("input[type='password']").first
            login_button = page.locator("button.login-btn, button[type='submit']").first

            # Aspettiamo che l'input dello username sia effettivamente pronto
            user_input.wait_for(state="visible", timeout=15000)

            # Eseguiamo un focus e una digitazione pulita
            user_input.focus()
            user_input.fill(username)
            page.wait_for_timeout(500)

            pass_input.focus()
            pass_input.fill(password)
            page.wait_for_timeout(500)

            print("[*] Click sul pulsante di accesso...")
            login_button.click()
            
            print("[*] Attesa reindirizzamento alla dashboard...")
            # FusionSolar dopo il login reindirizza a index.html
            page.wait_for_url("**/index.html**", timeout=35000)
            print("[+] Login completato con successo!")

            # Estrazione sessione
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
            print(f"[-] Errore durante la sessione: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot di errore aggiornato salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e