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
        # Avvio del browser con argomenti per disabilitare i flag di automazione
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9"
        )
        
        # Script per nascondere il flag webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # --- STEP 1: GESTIONE COOKIE ---
            print("[*] Verifico chiusura cookie/banner...")
            try:
                cookie_btn = page.locator("button:has-text('Accetta'), .pv-cookie-close, [aria-label='Close']").first
                if cookie_btn.is_visible():
                    cookie_btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # --- STEP 2: INSERIMENTO CREDENZIALI ---
            print("[*] Compilazione credenziali...")
            
            # Selettore generico per il primo input di testo visibile
            user_input = page.locator("input[type='text'], input[name*='user']").first
            user_input.wait_for(state="visible", timeout=15000)
            user_input.click()
            user_input.fill(USERNAME)
            page.wait_for_timeout(500)

            # Selettore per l'input password
            pwd_input = page.locator("input[type='password']").first
            pwd_input.wait_for(state="visible", timeout=15000)
            pwd_input.click()
            pwd_input.fill(PASSWORD)
            page.wait_for_timeout(500)

            # Screenshot di verifica compilazione
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- STEP 3: CLICK LOGIN ---
            print("[*] Esecuzione Login...")
            login_btn = page.locator("button:has-text('Accedi'), input[type='submit']").first
            if login_btn.is_visible():
                login_btn.click()
            else:
                pwd_input.press("Enter")

            print("[*] Attesa reindirizzamento...")
            page.wait_for_timeout(12000)

            # Screenshot dopo login
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
