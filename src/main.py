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

            # Cerca il frame corretto di UniSSO
            target = page
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target = frame
                    print(f"[+] Trovato frame dedicato: {frame.url}")
                    break

            # --- 1. USERNAME ---
            print("[*] Compilazione Username...")
            user_el = target.locator("input[type='text']:visible, input[placeholder*='utente']:visible").first
            user_el.wait_for(state="visible", timeout=10000)
            user_el.click()
            user_el.fill(USERNAME)
            
            # --- 2. PASSWORD ---
            print("[*] Compilazione Password...")
            pwd_el = target.locator("input[type='password']").first
            pwd_el.wait_for(state="attached", timeout=10000)

            page.keyboard.press("Tab")
            page.wait_for_timeout(200)
            page.keyboard.type(PASSWORD, delay=40)
            page.wait_for_timeout(200)

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

            page.wait_for_timeout(500)

            # --- 3. SELEZIONE REGION 004 ---
            print("[*] Selezione Region 004...")
            try:
                # Cerca il dropdown della region (attualmente mostra 'region003')
                region_dropdown = target.locator("text='region003'").first
                if region_dropdown.is_visible():
                    region_dropdown.click()
                    page.wait_for_timeout(500)
                    
                    # Clicca sull'opzione 'region004' nel menu a tendina aperto
                    opt_4 = target.locator("text='region004', li:has-text('004'), div:has-text('004')").first
                    if opt_4.is_visible():
                        opt_4.click()
                        print("[+] Selezionato region004 dal menu!")
                    else:
                        print("[!] Opzione region004 non trovata direttamente, invio della freccia giù...")
                        page.keyboard.press("ArrowDown")
                        page.keyboard.press("Enter")
            except Exception as reg_err:
                print(f"[!] Errore durante la selezione della regione: {reg_err}")

            page.wait_for_timeout(1000)

            # Screenshot di verifica compilazione con Region 4
            page.screenshot(path="pre_login_check.png")
            print("[+] Screenshot 'pre_login_check.png' salvato.")

            # --- 4. CLICK ACCEDI ---
            print("[*] Click su 'Accedi'...")
            btn = target.locator("button:has-text('Accedi'), .login-btn, input[type='submit'], div:has-text('Accedi')").first
            if btn.count() > 0 and btn.is_visible():
                btn.click(force=True)
            else:
                page.keyboard.press("Enter")

            print("[*] Attesa reindirizzamento Dashboard...")
            page.wait_for_timeout(15000)

            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato!")

        except Exception as e:
            print(f"[-] Errore catturato durante la procedura: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
