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

            # Individua il frame UniSSO
            target = page
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target = frame
                    print(f"[+] Frame UniSSO agganciato: {frame.url}")
                    break

            # --- USERNAME ---
            print("[*] Compilazione Username...")
            user_el = target.locator("input[type='text']:visible, input[placeholder*='utente']:visible").first
            user_el.wait_for(state="visible", timeout=10000)
            user_el.click()
            user_el.fill(USERNAME)
            
            # --- PASSWORD ---
            print("[*] Compilazione Password...")
            pwd_el = target.locator("input[type='password']").first
            pwd_el.wait_for(state="attached", timeout=10000)

            page.keyboard.press("Tab")
            page.wait_for_timeout(200)
            page.keyboard.type(PASSWORD, delay=30)
            page.wait_for_timeout(200)

            # Sincronizza lo stato React/Vue del form
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

            # --- SUBMIT NATIVO DEL FORM ---
            print("[*] Esecuzione Submit Nativo del Form di Login...")
            # Forziamo l'invio nativo via JavaScript su qualsiasi form presente nel frame
            target.evaluate("""
                () => {
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                    } else {
                        const btn = document.querySelector("button, input[type='submit'], .login-btn");
                        if (btn) btn.click();
                    }
                }
            """)

            # Fallback con invio tasto Enter da tastiera fisica
            page.keyboard.press("Enter")

            print("[*] Attesa caricamento dashboard (20 secondi)...")
            page.wait_for_timeout(20000)

            # Se compare un popup di avviso/cookie post-login, proviamo a chiuderlo
            try:
                page.locator("button:has-text('OK'), button:has-text('Conferma'), .nivo-close").click(timeout=3000)
            except Exception:
                pass

            # Screenshot finale
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' generato!")

        except Exception as e:
            print(f"[-] Errore catturato durante la procedura: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
