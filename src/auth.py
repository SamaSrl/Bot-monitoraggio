import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Esegue il login usando coordinate hardware, attende il caricamento
    generico della pagina e intercetta in modo pulito il popup di benvenuto.
    """
    print("[*] Avvio del browser in modalità hardware (Fix Timeout + Rimozione Popup)...")
    
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
            page.wait_for_timeout(3000)

            # --- 3. SPOSTAMENTO SU REGIONE VIA TAB ---
            print("[*] Navigazione sulla tendina della regione tramite tasto TAB...")
            page.keyboard.press("Tab")
            page.wait_for_timeout(1000)
            
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(1000)

            print("[*] Forzatura scrittura region004...")
            page.keyboard.type("region004", delay=150)
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # --- 4. CLICK SU ACCEDI ---
            print("[*] Invio del modulo di login...")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            
            print("[*] Clic di backup sul pulsante Accedi...")
            page.mouse.click(1300, 400)
            
            # --- 5. ATTESA CARICAMENTO POST-LOGIN RIGIDO ---
            print("[*] Attesa stabilizzazione della pagina post-login...")
            # Sostituiamo il selettore problematico aspettando semplicemente che la rete si calmi
            # o che compaia l'interfaccia di base del menu o del popup stesso
            page.wait_for_load_state("networkidle", timeout=45000)
            page.wait_for_timeout(5000) # 5 secondi extra per far renderizzare graficamente i popup

            # --- 6. RIMOZIONE POPUP DI BENVENUTO ---
            print("[*] Controllo presenza popup 'Aggiornamento della funzione'...")
            
            # Proviamo diversi selettori isolati e puliti per trovare il tasto "Non mostrare di nuovo"
            popup_selectors = [
                "text='Non mostrare di nuovo'",
                "button:has-text('Non mostrare di nuovo')",
                ".ant-btn:has-text('Non mostrare di nuovo')",
                ".ant-modal-close" # In alternativa la X di chiusura
            ]
            
            popup_closed = False
            for selector in popup_selectors:
                try:
                    locator = page.locator(selector).first
                    if locator.is_visible():
                        print(f"[+] Popup intercettato tramite selettore ({selector}). Clicco...")
                        locator.click()
                        page.wait_for_timeout(2000)
                        popup_closed = True
                        break
                except Exception:
                    continue

            if not popup_closed:
                print("[*] Nessun popup rilevato o già chiuso autonomamente.")

            # --- 7. ESTRAZIONE COOKIE ---
            print("[*] Estrazione cookie e token di sicurezza...")
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
                print("[*] Screenshot di controllo salvato in 'error_screenshot.png'.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e