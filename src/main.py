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
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # --- INIETTIAMO I DATI DIRETTAMENTE NEL DOM (Infallibile) ---
            print("[*] Inserimento credenziali diretto via JS...")
            
            page.evaluate(f"""
                () => {{
                    // Trova il campo username e imposta il valore
                    const userField = document.querySelector("input[name='ssoCredentials.username']") || document.querySelectorAll("input[type='text']")[0];
                    if (userField) {{
                        userField.value = '{USERNAME}';
                        userField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        userField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    
                    // Trova il campo password e imposta il valore
                    const pwdField = document.querySelector("input[name='ssoCredentials.password']") || document.querySelector("input[type='password']");
                    if (pwdField) {{
                        pwdField.value = '{PASSWORD}';
                        pwdField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        pwdField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
            """)
            page.wait_for_timeout(1000)

            # Salviamo lo screenshot PER VERIFICARE che i testi siano comparsi nei box!
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- PREMIAMO INVIO PER FARE IL LOGIN ---
            print("[*] Invio Form di Login...")
            page.keyboard.press("Enter")
            
            # Tentativo extra: click sul pulsante "Accedi"
            try:
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('button, span, a'));
                        const loginBtn = btns.find(el => el.textContent.trim() === 'Accedi');
                        if (loginBtn) loginBtn.click();
                    }
                """)
            except Exception:
                pass

            print("[*] Attesa reindirizzamento Dashboard...")
            page.wait_for_timeout(12000)

            # --- SCREENSHOT DELLA PAGINA DOPO IL LOGIN ---
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato.")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante il processo: {e}")
            page.screenshot(path="dashboard_check.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
