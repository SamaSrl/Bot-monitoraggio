import os
from playwright.sync_api import sync_playwright

# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def get_fusionsolar_session(username, password):
    """
    Usa Playwright simulando un browser umano reale e scansionando anche eventuali 
    iframe nidificati per trovare e compilare i campi di login di FusionSolar.
    """
    print("[*] Avvio del browser in modalità multi-frame (IT)...")
    
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
            
            print("[*] Attesa stabilizzazione interfaccia...")
            page.wait_for_timeout(8000) # Attesa per il caricamento completo degli script asincroni

            # 1. Identifichiamo dove si trovano i campi di testo (Page principale o iFrame?)
            user_selector = "input[placeholder*='utente'], input[placeholder*='e-mail'], input[type='text']"
            pass_selector = "input[placeholder*='Password'], input[placeholder*='password'], input[type='password']"
            login_btn_selector = "button:has-text('Accedi'), button[type='submit'], .login-btn"

            target = None

            # Controlliamo prima la pagina principale
            if page.locator(user_selector).count() > 0:
                print("[+] Campi rilevati nella pagina principale!")
                target = page
            else:
                # Se non sono sulla pagina principale, cerchiamo in tutti i frame/iframe caricati
                print("[*] Campi non trovati nella pagina principale. Scansione degli iframe in corso...")
                for frame in page.frames:
                    try:
                        if frame.locator(user_selector).count() > 0:
                            print(f"[+] Campi individuati con successo all'interno dell'iframe: {frame.name or frame.url}")
                            target = frame
                            break
                    except Exception:
                        continue

            # Se non abbiamo trovato i campi da nessuna parte, lanciamo un errore per fare lo screenshot di debug
            if not target:
                raise Exception("Impossibile trovare i campi di login (user/password) sia nella pagina principale sia negli iframe.")

            # 2. Compilazione dei campi sul target individuato
            print("[*] Inserimento credenziali sul target...")
            target.locator(user_selector).first.click()
            target.locator(user_selector).first.fill(username)
            page.wait_for_timeout(1000)

            target.locator(pass_selector).first.click()
            target.locator(pass_selector).first.fill(password)
            page.wait_for_timeout(1000)

            print("[*] Click sul pulsante 'Accedi'...")
            target.locator(login_btn_selector).first.click()
            
            print("[*] Attesa reindirizzamento alla dashboard...")
            page.wait_for_url("**/index.html**", timeout=35000)
            print("[+] Login completato con successo!")

            # Estrazione cookie e token
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
                print("[*] Screenshot di errore salvato.")
            except Exception as screenshot_err:
                print(f"[-] Impossibile scattare lo screenshot: {screenshot_err}")
            
            browser.close()
            raise e