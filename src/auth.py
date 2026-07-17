import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright simulando un browser umano reale per bypassare i blocchi script.
    """
    print("[*] Avvio del browser in modalità camuffata...")
    
    with sync_playwright() as p:
        # Lanciamo chromium imitando un utente reale su Windows
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            timezone_id="Europe/Rome",
            extra_http_headers={
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )
        
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            # Diamo fino a 60 secondi per caricare tutto a causa della latenza dei server remoti
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            
            print("[*] Attesa stabilizzazione degli script della pagina...")
            page.wait_for_timeout(7000) # 7 secondi di attesa forzata per far svegliare i moduli JavaScript

            print("[*] Inserimento credenziali...")
            
            # Utilizziamo una strategia di inserimento mista: prima clicchiamo, poi scriviamo
            user_selector = "input[type='text'], input[placeholder*='User'], .username-input input"
            page.wait_for_selector(user_selector, timeout=15000)
            
            page.click(user_selector)
            page.locator(user_selector).first.fill(username)
            page.wait_for_timeout(5000) # Pausa di controllo

            pass_selector = "input[type='password'], input[placeholder*='Pass'], .password-input input"
            page.click(pass_selector)
            page.locator(pass_selector).first.fill(password)
            page.wait_for_timeout(5000)

            print("[*] Click sul pulsante Log In...")
            login_btn = page.locator("button:has-text('Log In'), button[type='submit'], .login-btn").first
            login_btn.click()
            
            print("[*] Attesa reindirizzamento alla dashboard...")
            page.wait_for_url("**/index.html**", timeout=30000)
            print("[+] Login completato con successo!")

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
            print(f"[-] Errore durante la sessione camuffata: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Nuovo screenshot di errore salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e