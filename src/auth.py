import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright simulando clic fisici a coordinate per forzare l'attivazione
    dei campi di login nascosti di FusionSolar.
    """
    print("[*] Avvio del browser in modalità simulazione hardware...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Fissiamo la risoluzione a 1920x1080 per calcolare precisamente le coordinate
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
            
            print("[*] Attesa rendering completo della pagina...")
            page.wait_for_timeout(10000) # 10 secondi pieni per essere sicuri che la grafica sia stabile

            print("[*] Forzatura attivazione campi tramite clic a coordinate fisiche...")
            
            # Con una risoluzione di 1920x1080, la barra bianca del login si trova esattamente al centro orizzontale (X ~ 960)
            # e leggermente sopra la metà verticale (Y ~ 400).
            # Muoviamo il mouse e clicchiamo lì per "svegliare" l'input dell'utente.
            page.mouse.move(850, 400)
            page.mouse.click(850, 400)
            page.wait_for_timeout(1000)
            
            # Proviamo a digitare direttamente con la tastiera hardware nel punto cliccato
            print("[*] Digitazione username via hardware...")
            page.keyboard.type(username, delay=100)
            page.wait_for_timeout(1000)

            # Ci spostiamo leggermente a destra sulla stessa barra per attivare la password (X ~ 1070)
            page.mouse.move(1070, 400)
            page.mouse.click(1070, 400)
            page.wait_for_timeout(1000)
            
            print("[*] Digitazione password via hardware...")
            page.keyboard.type(password, delay=100)
            page.wait_for_timeout(1000)

            print("[*] Invio del modulo tramite tasto Enter...")
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            # Clic di backup sul pulsante blu "Accedi" (si trova a destra della barra, X ~ 1300, Y ~ 400)
            try:
                page.mouse.click(1300, 400)
            except Exception:
                pass

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
            print(f"[-] Errore durante la sessione hardware: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot aggiornato salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e