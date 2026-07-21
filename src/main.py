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
                "--disable-setuid-sandbox",
                "--disable-web-security"
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
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            # Cerca il frame corretto (Iframe UniSSO o Pagina Principale)
            target = page
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target = frame
                    print(f"[+] Trovato frame dedicato: {frame.url}")
                    break

            # --- COMPILAZIONE USERNAME ---
            print("[*] Compilazione Username...")
            user_el = target.locator("input[type='text']:visible, input[placeholder*='utente']:visible").first
            user_el.wait_for(state="visible", timeout=10000)
            user_el.click()
            user_el.fill(USERNAME)
            
            # --- COMPILAZIONE PASSWORD VIA EVENTI JS E TASTIERA ---
            print("[*] Compilazione Password...")
            pwd_el = target.locator("input[type='password']").first
            pwd_el.wait_for(state="attached", timeout=10000)

            # 1. Spostiamo il focus usando la tastiera (Tab)
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)

            # 2. Scriviamo la password tasto per tasto
            page.keyboard.type(PASSWORD, delay=50)
            page.wait_for_timeout(300)

            # 3. Forziamo l'aggiornamento dello stato interno via JS
            target.evaluate("""
                (pwdValue) => {
                    const pwdInput = document.querySelector("input[type='password']");
                    if (pwdInput) {
                        pwdInput.value = pwdValue;
                        pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
                        pwdInput.dispatchEvent(new Event('change', { bubbles: true }));
                        pwdInput.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                }
            """, PASSWORD)

            page.wait_for_timeout(1000)

            # Screenshot di verifica compilazione
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- INVIO E LOGIN ---
            print("[*] Tentativo di Invio Login...")
            
            # Clicchiamo sul pulsante 'Accedi' visibile
            btn = target.locator("button:has-text('Accedi'), .login-btn, input[type='submit']").first
            if btn.count() > 0 and btn.is_visible():
                btn.click(force=True)
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(5000)
            page.screenshot(path="after_submit_check.png")
            print("[+] Screenshot 'after_submit_check.png' salvato.")

            # Attesa finale reindirizzamento
            page.wait_for_timeout(10000)
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato.")

        except Exception as e:
            print(f"[-] Errore catturato durante la procedura: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
