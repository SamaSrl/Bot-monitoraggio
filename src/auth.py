import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Esegue il login usando coordinate hardware stabili per i campi di testo,
    usa il tasto TAB per selezionare la regione e gestisce la dashboard.
    """
    print("[*] Avvio del browser in modalità simulazione hardware (Fix Regione via TAB)...")
    
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
            page.wait_for_timeout(8000)

            # --- 1. COMPILAZIONE USERNAME ---
            print("[*] Inserimento Username...")
            page.mouse.move(850, 400)
            page.mouse.click(850, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(username, delay=100)
            page.wait_for_timeout(1000)

            # --- 2. COMPILAZIONE PASSWORD ---
            print("[*] Inserimento Password...")
            page.mouse.move(1070, 400)
            page.mouse.click(1070, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(password, delay=100)
            page.wait_for_timeout(3000) # Aspettiamo che appaia visivamente il box region003

            # --- 3. SPOSTAMENTO SU REGIONE VIA TAB ---
            print("[*] Navigazione sulla tendina della regione tramite tasto TAB...")
            page.keyboard.press("Tab")
            page.wait_for_timeout(1000)
            
            # Inviamo una freccia giù per aprire/attivare il menu
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(1000)

            print("[*] Forzatura scrittura region004...")
            # Cancelliamo un eventuale valore parziale e scriviamo la regione corretta
            page.keyboard.type("region004", delay=150)
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # --- 4. CLICK SU ACCEDI VIA COORD/ENTER ---
            print("[*] Invio del modulo di login...")
            # Proviamo prima premendo Enter dalla tastiera che è rimasta agganciata al modulo
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            
            # Clic di sicurezza sul pulsante blu a destra (X=1300, Y=400)
            print("[*] Clic di backup sul pulsante Accedi...")
            page.mouse.click(1300, 400)
            
            # --- 5. VERIFICA DASHBOARD & POPUP ---
            print("[*] Attesa caricamento della Dashboard...")
            page.wait_for_selector("text=Monitoraggio, text=Impianti, .ant-layout", timeout=45000)
            print("[+] Accesso alla Dashboard confermato!")
            page.wait_for_timeout(4000)

            print("[*] Controllo eventuale popup di benvenuto...")
            btn_chiudi_popup = page.locator("button:has-text('Non mostrare di nuovo'), .ant-modal-close, text=Non mostrare di nuovo").first
            if btn_chiudi_popup.is_visible():
                print("[+] Popup rilevato. Chiusura in corso...")
                btn_chiudi_popup.click()
                page.wait_for_timeout(2000)

            # --- 6. ESTRAZIONE cookie ---
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            xsrf_token = ""
            for cookie in cookies:
                if cookie['name'] == 'XSRF-TOKEN':
                    xsrf_token = cookie['value']
                    break

            print("[+] Sessione catturata con successo!")
            browser.close()
            return session_cookies, xsrf_token

        except Exception as e:
            print(f"[-] Errore durante la sessione: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot di controllo salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e