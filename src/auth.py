import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright simulando un browser umano reale e iniettando le credenziali
    direttamente nel codice della pagina italiana per superare i blocchi grafici.
    """
    print("[*] Avvio del browser in modalità camuffata (IT)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9",
            timezone_id="Europe/Rome",
            extra_http_headers={
                "Accept-Language": "it-IT,it;q=0.9"
            }
        )
        
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            
            print("[*] Attesa stabilizzazione interfaccia italiana...")
            page.wait_for_timeout(8000) # 8 secondi per garantire il caricamento degli script asincroni

            print("[*] Compilazione credenziali tramite iniettore...")
            
            # Selettori universali per la versione italiana basati sui nuovi placeholder e classi
            user_selector = "input[placeholder*='utente'], input[placeholder*='e-mail'], input[type='text']"
            pass_selector = "input[placeholder*='Password'], input[placeholder*='password'], input[type='password']"
            
            page.wait_for_selector(user_selector, timeout=15000)

            # METODO DI FORZATURA JS: Inietta il testo direttamente nell'elemento DOM per evitare blocchi grafici
            page.evaluate(f"""
                (userSel, passSel, userVal, passVal) => {{
                    const uField = document.querySelector(userSel);
                    const pField = document.querySelector(passSel);
                    if(uField) {{
                        uField.value = userVal;
                        uField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        uField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    if(pField) {{
                        pField.value = passVal;
                        pField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        pField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
            """, user_selector, pass_selector, username, password)
            
            page.wait_for_timeout(2000) # Pausa per registrare i dati inseriti

            print("[*] Click sul pulsante 'Accedi'...")
            # Clicca sul vistoso bottone blu che ora riporta il testo "Accedi"
            login_btn = page.get_by_role("button", name="Accedi").or_(page.locator("button:has-text('Accedi')")).or_(page.locator(".login-btn")).first
            login_btn.click()
            
            print("[*] Attesa reindirizzamento alla dashboard...")
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
            print(f"[-] Errore durante la sessione italiana: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot aggiornato salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e