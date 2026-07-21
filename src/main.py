import os
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    print("[*] Avvio Bot Monitoraggio FusionSolar (Stealth Mode)...")
    
    with sync_playwright() as p:
        # Configurazione Browser con bypass anti-bot avanzato
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT",
            timezone_id="Europe/Rome"
        )
        
        # Script di mascheramento proprietà webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            # 1. Trova ed evidenzia il campo Username
            print("[*] Ricerca campo Username...")
            inputs = page.locator("input").all()
            print(f"[*] Trovati {len(inputs)} campi input nella pagina.")

            # Tenta la ricerca selettiva
            user_input = page.locator("input[type='text']").first
            user_input.wait_for(state="attached", timeout=10000)
            
            # Focus, pulizia e digitazione simulata tasto per tasto
            user_input.focus()
            page.wait_for_timeout(300)
            user_input.press("Control+a")
            user_input.press("Backspace")
            
            for char in USERNAME:
                page.keyboard.type(char, delay=50)
            page.wait_for_timeout(500)

            # 2. Trova ed evidenzia il campo Password
            print("[*] Ricerca campo Password...")
            pwd_input = page.locator("input[type='password']").first
            pwd_input.focus()
            page.wait_for_timeout(300)
            pwd_input.press("Control+a")
            pwd_input.press("Backspace")
            
            for char in PASSWORD:
                page.keyboard.type(char, delay=50)
            page.wait_for_timeout(500)

            # Salva screenshot della compilazione prima del click
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato con successo.")

            # 3. Invio credenziali via Invio da tastiera
            print("[*] Invio form con Enter...")
            pwd_input.press("Enter")
            
            # Attesa di caricamento ed eventuale reindirizzamento
            page.wait_for_timeout(15000)

            # Screenshot finale post-login
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
