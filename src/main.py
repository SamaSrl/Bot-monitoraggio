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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9"
        )
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # --- PASSO 1: COMPILAZIONE USERNAME ---
            print("[*] Inserimento Username...")
            user_input = page.locator("input[placeholder*='Account'], input[placeholder*='Username'], input[type='text']").first
            user_input.fill(USERNAME)
            page.wait_for_timeout(500)

            # --- PASSO 2: COMPILAZIONE PASSWORD ---
            print("[*] Inserimento Password...")
            pwd_input = page.locator("input[type='password']").first
            pwd_input.fill(PASSWORD)
            page.wait_for_timeout(500)

            # --- PASSO 3: CLICK SUL PULSANTE ACCEDI ---
            print("[*] Click su 'Accedi'...")
            login_btn = page.locator("button:has-text('Accedi'), button:has-text('Log In'), span:has-text('Accedi')").first
            if login_btn.is_visible():
                login_btn.click()
            else:
                page.keyboard.press("Enter")

            # Attesa di caricamento dopo il login
            print("[*] Attesa risposta dal server...")
            page.wait_for_timeout(8000)

            # --- PASSO 4: SCREENSHOT DI VERIFICA ---
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo!")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante il processo: {e}")
            page.screenshot(path="dashboard_check.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
