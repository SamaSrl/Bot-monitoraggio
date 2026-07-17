import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright simulando interazioni hardware pure per inserire le credenziali,
    aprire la tendina regionale, selezionare la 'region004' e completare il login.
    """
    print("[*] Avvio del browser in modalità simulazione hardware (Forzatura Region004)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Fissiamo la risoluzione per garantire che le coordinate siano precise al millimetro
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
            
            print("[*] Attesa rendering iniziale...")
            page.wait_for_timeout(8000)

            # --- FASE 1: INSERIMENTO USERNAME ---
            print("[*] Compilazione campo Username...")
            page.mouse.move(850, 400)
            page.mouse.click(850, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(username, delay=100)
            page.wait_for_timeout(1000)

            # --- FASE 2: INSERIMENTO PASSWORD ---
            print("[*] Compilazione campo Password...")
            page.mouse.move(1070, 400)
            page.mouse.click(1070, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(password, delay=100)
            
            # --- FASE 3: ATTESA E APERTURA TENDINA REGIONE ---
            print("[*] Attesa comparsa selettore regionale...")
            page.wait_for_timeout(4000) # Tempo necessario affinché compaia il box "region003" sotto i campi

            print("[*] Clic sul menu a tendina della regione...")
            # Basandoci sullo screenshot, il box della regione si trova centrato orizzontalmente sotto i campi
            # Coordinate stimate: X=960 (centro dello schermo), Y=415 (subito sotto la barra di login)
            page.mouse.move(960, 415)
            page.mouse.click(960, 415)
            page.wait_for_timeout(1500) # Aspettiamo che la tendina si apra graficamente

            # --- FASE 4: SELEZIONE DI REGION004 ---
            print("[*] Tentativo di digitazione diretta della regione...")
            # Spesso queste tendine permettono di cercare scrivendo. Proviamo a digitare "region004"
            page.keyboard.type("region004", delay=100)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Come metodo di backup se la digitazione non ha filtrato, usiamo le frecce direzionali
            # (Solitamente premendo Freccia Giù una o due volte ci si sposta tra le opzioni disponibili)
            print("[*] Invio comandi di navigazione da tastiera per sicurezza...")
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # --- FASE 5: CLIC SU ACCEDI ---
            print("[*] Clic sul pulsante 'Accedi'...")
            # Il pulsante blu "Accedi" si trova a destra (X=1300, Y=400)
            page.mouse.move(1300, 400)
            page.mouse.click(1300, 400)
            
            print("[*] Attesa reindirizzamento alla dashboard...")
            # Monitoriamo sia l'URL che eventuali cambiamenti di pagina
            page.wait_for_url("**/index.html**", timeout=40000)
            print("[+] Login completato con successo su region004!")

            # Estrazione cookie e token di sessione
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
                print("[*] Nuovo screenshot di errore salvato in 'error_screenshot.png'.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e