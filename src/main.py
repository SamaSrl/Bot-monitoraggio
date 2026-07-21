import os
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    print("[*] Avvio Bot Monitoraggio FusionSolar...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT"
        )
        
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)

            # --- IDENTIFICAZIONE TELAIO (IFRAME) DI LOGIN ---
            print(f"[*] Numero di frame trovati nella pagina: {len(page.frames)}")
            
            target_frame = None
            for frame in page.frames:
                try:
                    # Cerchiamo il frame che possiede un input di tipo password o testo
                    if frame.locator("input[type='password']").count() > 0:
                        target_frame = frame
                        print(f"[+] Frame di login trovato: {frame.url}")
                        break
                except Exception:
                    continue

            # Se non trova un iframe specifico, lavora sulla pagina principale
            if not target_frame:
                print("[!] Nessun iframe specifico individuato, utilizzo la pagina principale.")
                target_frame = page

            # --- GESTIONE COOKIE SUL FRAME IDENTIFICATO ---
            try:
                cookie_btn = target_frame.locator("button:has-text('Accetta'), .pv-cookie-close, [aria-label='Close']").first
                if cookie_btn.is_visible():
                    cookie_btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # --- INSERIMENTO CREDENZIALI NELLO SCOPE CORRETTO ---
            print("[*] Inserimento Username...")
            user_input = target_frame.locator("input[type='text'], input[name*='user'], input[placeholder*='utente']").first
            user_input.wait_for(state="attached", timeout=10000)
            user_input.click(force=True)
            user_input.fill("")
            user_input.type(USERNAME, delay=40)
            page.wait_for_timeout(500)

            print("[*] Inserimento Password...")
            pwd_input = target_frame.locator("input[type='password']").first
            pwd_input.wait_for(state="attached", timeout=10000)
            pwd_input.click(force=True)
            pwd_input.fill("")
            pwd_input.type(PASSWORD, delay=40)
            page.wait_for_timeout(500)

            # Screenshot di verifica compilazione
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- CLICK LOGIN ---
            print("[*] Invio login...")
            login_btn = target_frame.locator("button:has-text('Accedi'), input[type='submit'], .login-btn").first
            if login_btn.is_visible():
                login_btn.click(force=True)
            else:
                pwd_input.press("Enter")

            print("[*] Attesa reindirizzamento...")
            page.wait_for_timeout(15000)

            # Screenshot post-login
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato.")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'esecuzione: {e}")
            page.screenshot(path="dashboard_check.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
