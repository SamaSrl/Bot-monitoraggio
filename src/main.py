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
            page.wait_for_timeout(5000)

            # Cerca l'iframe di login
            target_frame = None
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target_frame = frame
                    print(f"[+] Frame di login individuato: {frame.url}")
                    break

            if not target_frame:
                target_frame = page

            page.wait_for_timeout(2000)

            # --- STEP 1: USERNAME ---
            print("[*] Inserimento Username...")
            user_input = target_frame.locator("input[type='text']:visible, input#username").first
            user_input.wait_for(state="visible", timeout=10000)
            user_input.focus()
            user_input.fill(USERNAME)
            print("[+] Username inserito.")
            page.wait_for_timeout(500)

            # --- STEP 2: PASSWORD ---
            print("[*] Inserimento Password...")
            pwd_input = target_frame.locator("input[type='password']").first
            pwd_input.wait_for(state="attached", timeout=10000)
            
            # Usiamo focus + press_sequentially senza fare click
            pwd_input.focus()
            page.wait_for_timeout(200)
            pwd_input.fill("")
            pwd_input.press_sequentially(PASSWORD, delay=50)
            print("[+] Password inserita.")
            page.wait_for_timeout(500)

            # Salviamo lo screenshot di verifica con entrambi i campi compilati
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- STEP 3: LOGIN ---
            print("[*] Invio form di Login...")
            # Proviamo prima a premere Enter sul campo password
            pwd_input.press("Enter")
            
            # Se dopo 3 secondi siamo ancora nella stessa pagina, clicchiamo il pulsante Accedi
            page.wait_for_timeout(3000)
            login_btn = target_frame.locator("button:visible, input[type='submit']:visible, .btn-login:visible, #loginBtn, a:has-text('Accedi')").first
            if login_btn.count() > 0 and login_btn.is_visible():
                login_btn.click(force=True)

            print("[*] Attesa reindirizzamento Dashboard...")
            page.wait_for_timeout(15000)

            # Salviamo lo screenshot della Dashboard dopo il login
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo!")

        except Exception as e:
            print(f"[-] Errore durante l'esecuzione: {e}")
            # In caso di errore salviamo comunque lo screenshot dello stato attuale
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
