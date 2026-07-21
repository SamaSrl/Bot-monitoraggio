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

            # Cerca l'iframe di login di Huawei
            target_frame = None
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target_frame = frame
                    print(f"[+] Frame di login individuato: {frame.url}")
                    break

            if not target_frame:
                target_frame = page
                print("[!] Uso pagina principale.")

            page.wait_for_timeout(2000)

            # --- COMPILAZIONE CAMPO USERNAME VISIBILE ---
            print("[*] Ricerca campo Username visibile...")
            # Usa il filtro :visible per scartare gli input nascosti nel DOM
            user_input = target_frame.locator("input[type='text']:visible, input#username, input[name='username']:visible").first
            user_input.wait_for(state="visible", timeout=10000)
            user_input.click()
            user_input.fill(USERNAME)
            print("[+] Username inserito.")

            # --- COMPILAZIONE CAMPO PASSWORD VISIBILE ---
            print("[*] Ricerca campo Password visibile...")
            pwd_input = target_frame.locator("input[type='password']:visible, input#password").first
            pwd_input.wait_for(state="visible", timeout=10000)
            pwd_input.click()
            pwd_input.fill(PASSWORD)
            print("[+] Password inserita.")

            # Salva lo screenshot con i campi compilati prima dell'invio
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- INVIO FORM ---
            print("[*] Invio credenziali...")
            login_btn = target_frame.locator("button:visible, input[type='submit']:visible, .btn-login:visible, #loginBtn").first
            if login_btn.count() > 0 and login_btn.is_visible():
                login_btn.click()
            else:
                pwd_input.press("Enter")

            print("[*] Attesa risposta del server...")
            page.wait_for_timeout(12000)

        except Exception as e:
            print(f"[-] Errore intercettato durante la procedura: {e}")

        finally:
            # Viene eseguito SEMPRE per garantire la creazione dello screenshot
            print("[*] Generazione screenshot finale di controllo...")
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo!")
            browser.close()

if __name__ == "__main__":
    main()
