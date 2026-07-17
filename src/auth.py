import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Esegue il login simulando l'hardware, seleziona la region004,
    abbatte eventuali popup di notifica iniziali ed estrae la sessione.
    """
    print("[*] Avvio del browser in modalità hardware (Region004 + Gestione Popup)...")
    
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

            # --- 1. COMPILAZIONE LOGIN VIA HARDWARE ---
            print("[*] Inserimento Username...")
            page.mouse.click(850, 400)
            page.keyboard.type(username, delay=100)
            page.wait_for_timeout(1000)

            print("[*] Inserimento Password...")
            page.mouse.click(1070, 400)
            page.keyboard.type(password, delay=100)
            page.wait_for_timeout(4000) 

            # --- 2. GESTIONE SELEZIONE REGIONE ---
            print("[*] Apertura menu regione...")
            page.mouse.click(960, 415)
            page.wait_for_timeout(1500) 

            print("[*] Selezione forzata di region004...")
            page.keyboard.type("region004", delay=100)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # --- 3. CLICK SU ACCEDI ---
            print("[*] Click sul pulsante 'Accedi'...")
            page.mouse.click(1300, 400)
            
            # Attendiamo che la pagina principale si carichi (aspettiamo che appaia il menu superiore)
            print("[*] Attesa caricamento della Dashboard...")
            page.wait_for_selector("text=Monitoraggio, text=Impianti, .ant-layout", timeout=45000)
            print("[+] Accesso alla Dashboard rilevato con successo!")
            page.wait_for_timeout(3000) # Lasciamo stabilizzare l'interfaccia grafica

            # --- 4. ABBATTIMENTO POPUP DI BENVENUTO ---
            print("[*] Controllo presenza popup 'Aggiornamento della funzione'...")
            # Cerchiamo il pulsante "Non mostrare di nuovo" o la X di chiusura
            btn_chiudi_popup = page.locator("button:has-text('Non mostrare di nuovo'), .ant-modal-close, text=Non mostrare di nuovo").first
            
            if btn_chiudi_popup.is_visible():
                print("[+] Popup rilevato! Clicco per chiuderlo...")
                btn_chiudi_popup.click()
                page.wait_for_timeout(2000)
            else:
                print("[*] Nessun popup visibile in primo piano.")

            # --- 5. ESTRAZIONE SESSIONE ---
            print("[*] Estrazione cookie e token di sicurezza...")
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            xsrf_token = ""
            for cookie in cookies:
                if cookie['name'] == 'XSRF-TOKEN':
                    xsrf_token = cookie['value']
                    break

            print("[+] Sessione catturata ed estratta con successo!")
            browser.close()
            return session_cookies, xsrf_token

        except Exception as e:
            print(f"[-] Errore durante la sessione post-login: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
                print("[*] Screenshot di debug salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e